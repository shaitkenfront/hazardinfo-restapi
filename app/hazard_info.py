import requests
import json
import math
import os
import time
from PIL import Image
from io import BytesIO
from shapely.geometry import shape, Point, Polygon
from concurrent.futures import ThreadPoolExecutor
from rtree import index
from app import geocoding, geojsonhelper

# 分離したモジュールからインポート
from app.config.constants import (
    TILE_SIZE,
    SEARCH_RADIUS_METERS,
    HIGH_PRECISION_SEARCH_POINTS,
    STANDARD_SEARCH_POINTS,
    HTTP_TIMEOUT_SECONDS,
    THREAD_TIMEOUT_SECONDS,
    HIGH_PRECISION_FALLBACK_POINTS,
    MAX_WORKERS_THREAD_POOL,
    JSHIS_API_URL_BASE,
    WMS_GETFEATUREINFO_BASE_URL,
    TILE_CONFIGS,
    # 後方互換性のための個別定数
    FLOOD_TILE_URL,
    FLOOD_TILE_ZOOM,
    FLOOD_L1_TILE_URL,
    DEBRIS_FLOW_TILE_URL,
    DEBRIS_FLOW_TILE_ZOOM,
    STEEP_SLOPE_TILE_URL,
    STEEP_SLOPE_TILE_ZOOM,
    LANDSLIDE_TILE_URL,
    LANDSLIDE_TILE_ZOOM,
    TSUNAMI_TILE_URL,
    TSUNAMI_TILE_ZOOM,
    HIGH_TIDE_TILE_URL,
    HIGH_TIDE_TILE_ZOOM,
    FLOOD_KEIZOKU_TILE_URL,
    FLOOD_KEIZOKU_TILE_ZOOM,
    KAOKUTOUKAI_HANRAN_TILE_URL,
    KAOKUTOUKAI_HANRAN_TILE_ZOOM,
)
from app.utils.color_mapping import (
    WATER_DEPTH_COLOR_MAP,
    INUNDATION_COLOR_MAP,
    TSUNAMI_COLOR_MAP,
    HIGH_TIDE_COLOR_MAP,
    FLOOD_INUNDATION_COLOR_MAP,
    DEBRIS_FLOW_COLOR_MAP,
    STEEP_SLOPE_COLOR_MAP,
    LANDSLIDE_COLOR_MAP,
    FLOOD_KEIZOKU_COLOR_MAP,
)
from app.utils.tile_utils import (
    latlon_to_gsi_tile_pixel,
    fetch_single_tile,
    get_points_in_radius,
    fetch_tiles_parallel,
)

# 後方互換性のために関数エイリアスを保持
_fetch_single_tile = fetch_single_tile
_get_points_in_radius = get_points_in_radius

# 大規模盛土造成地
ENABLE_LARGE_FILL_LAND = (
    os.environ.get("ENABLE_LARGE_FILL_LAND", "false").lower() == "true"
)
S3_LARGE_FILL_LAND_BUCKET = os.environ.get("S3_LARGE_FILL_LAND_BUCKET")
S3_LARGE_FILL_LAND_FOLDER = "A54-23_GEOJSON"
S3_LARGE_FILL_LAND_FILE_PREFIX = "A54-23_"




def build_polygon(img):
    """
    Parameters
    ----------
    img : PIL.Image.Image
        赤線が (255, 0, 0) のみで描かれた画像

    Returns
    -------
    shapely.geometry.Polygon
        赤線外周を多角形近似したポリゴン
    """
    w, h = img.size
    pixels = list(img.getdata())

    # 1) 完全赤画素を収集
    red = set()
    for y in range(h):
        offset = y * w
        for x in range(w):
            if pixels[offset + x] == (255, 0, 0):
                red.add((x, y))

    # 2) 外周だけ抽出（4近傍に非赤があれば境界）
    border = []
    for x, y in red:
        nbr = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
        if any((nx, ny) not in red for nx, ny in nbr):
            border.append((x, y))

    # 3) ポリゴン化し、buffer(0) で自己交差を解消
    return Polygon(border).buffer(0)

def is_inside(x, y, poly):
    """
    Parameters
    ----------
    x, y : int
        判定したい画像内座標
    poly : shapely.geometry.Polygon
        build_polygon() で得たポリゴン

    Returns
    -------
    bool
        True なら赤線に囲まれた内部、False なら外部
    """
    return poly.contains(Point(x, y))



def _fetch_jshis_data(
    lat: float, lon: float, timeout: int = HTTP_TIMEOUT_SECONDS
) -> tuple[float | None, float | None]:
    """
    単一の地点のJ-SHISデータを取得するヘルパー関数
    """
    params_50 = {
        "position": f"{lon},{lat}",
        "epsg": 4326,
    }
    params_60 = {
        "position": f"{lon},{lat}",
        "epsg": 4326,
    }

    prob_50 = None
    prob_60 = None

    try:
        response_50 = requests.get(
            JSHIS_API_URL_BASE, params=params_50, timeout=timeout
        )
        response_50.raise_for_status()
        geojson_50 = response_50.json()

        if geojson_50.get("features") and geojson_50["features"][0].get("properties"):
            prob_50_val = geojson_50["features"][0]["properties"].get("T30_I50_PS")
            if prob_50_val is not None:
                prob_50 = float(prob_50_val)
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching J-SHIS 50 data for {lat},{lon}: {e}")

    try:
        response_60 = requests.get(
            JSHIS_API_URL_BASE, params=params_60, timeout=timeout
        )
        response_60.raise_for_status()
        geojson_60 = response_60.json()

        if geojson_60.get("features") and geojson_60["features"][0].get("properties"):
            prob_60_val = geojson_60["features"][0]["properties"].get("T30_I60_PS")
            if prob_60_val is not None:
                prob_60 = float(prob_60_val)
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching J-SHIS 60 data for {lat},{lon}: {e}")

    return prob_50, prob_60


def _get_max_info_from_tile(
    lat: float,
    lon: float,
    tile_url_template: str,
    tile_zoom: int,
    color_map: dict,
    no_risk_description: str,
    high_precision: bool = False,
) -> dict:
    """
    指定されたタイルソースから情報を取得する汎用関数。

    high_precision=False: 中心点とその周囲8方位のピクセルを調査（高速）
    high_precision=True: 周辺100m範囲内の全ピクセルを密度の高いサンプリングで調査（高精度）
    """
    if high_precision:
        return _get_max_info_from_tile_high_precision(
            lat, lon, tile_url_template, tile_zoom, color_map, no_risk_description
        )
    else:
        return _get_max_info_from_tile_8_directions(
            lat, lon, tile_url_template, tile_zoom, color_map, no_risk_description
        )


def _get_max_info_from_tile_8_directions(
    lat: float,
    lon: float,
    tile_url_template: str,
    tile_zoom: int,
    color_map: dict,
    no_risk_description: str,
) -> dict:
    """
    中心点とその周囲8方位のピクセルを調査する高速版
    """
    # 中心点の座標を取得
    zoom, x_tile, y_tile, center_px, center_py = latlon_to_gsi_tile_pixel(
        lat, lon, tile_zoom
    )

    # タイルを取得
    tile_url = tile_url_template.format(z=zoom, x=x_tile, y=y_tile)
    img = _fetch_single_tile(tile_url, HTTP_TIMEOUT_SECONDS)

    if img is None:
        return {"max_info": no_risk_description, "center_info": no_risk_description}

    max_info = {"description": no_risk_description, "weight": 0}
    center_info = {"description": no_risk_description, "weight": 0}

    # チェックするピクセル座標（中心点 + 8方位）
    pixel_offsets = [
        (0, 0),  # 中心点
        (-1, -1),  # 北西
        (0, -1),  # 北
        (1, -1),  # 北東
        (1, 0),  # 東
        (1, 1),  # 南東
        (0, 1),  # 南
        (-1, 1),  # 南西
        (-1, 0),  # 西
    ]

    for i, (dx, dy) in enumerate(pixel_offsets):
        is_center_point = i == 0
        px = center_px + dx
        py = center_py + dy

        # 境界チェック
        if px < 0 or px >= TILE_SIZE or py < 0 or py >= TILE_SIZE:
            continue

        try:
            r, g, b, a = img.getpixel((px, py))
            pixel_rgb = (r, g, b)
            current_info = {"description": "情報なし", "weight": -1}

            if pixel_rgb in color_map:
                current_info = color_map[pixel_rgb]
            elif a == 0:
                current_info = {"description": no_risk_description, "weight": 0}

            if is_center_point:
                center_info = current_info

            if current_info["weight"] > max_info["weight"]:
                max_info = current_info

        except Exception as e:
            print(f"ERROR: Failed to process pixel at ({px}, {py}). Error: {e}")
            if is_center_point:
                center_info = {"description": no_risk_description, "weight": 0}

    return {
        "max_info": max_info["description"],
        "center_info": center_info["description"],
    }


def _get_max_info_from_tile_high_precision(
    lat: float,
    lon: float,
    tile_url_template: str,
    tile_zoom: int,
    color_map: dict,
    no_risk_description: str,
) -> dict:
    """
    周辺100m範囲内の全ピクセルを密度の高いサンプリングで調査する高精度版
    """
    # 半径100mの範囲内で16点のサンプリング点を生成
    search_points = _get_points_in_radius(lat, lon, SEARCH_RADIUS_METERS, HIGH_PRECISION_SEARCH_POINTS)

    tiles_to_fetch = {}
    for p_lat, p_lon in search_points:
        zoom, x_tile, y_tile, _, _ = latlon_to_gsi_tile_pixel(p_lat, p_lon, tile_zoom)
        if (zoom, x_tile, y_tile) not in tiles_to_fetch:
            tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    # タイルを並列取得
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREAD_POOL) as executor:
        futures = {}
        for zoom, x_tile, y_tile in tiles_to_fetch.keys():
            tile_url = tile_url_template.format(z=zoom, x=x_tile, y=y_tile)
            future = executor.submit(_fetch_single_tile, tile_url, HTTP_TIMEOUT_SECONDS)
            futures[(zoom, x_tile, y_tile)] = future

        # 結果を収集
        for (zoom, x_tile, y_tile), future in futures.items():
            try:
                tiles_to_fetch[(zoom, x_tile, y_tile)] = future.result(timeout=THREAD_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"Error fetching tile {zoom}/{x_tile}/{y_tile}: {e}")
                tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    max_info = {"description": no_risk_description, "weight": 0}
    center_info = {"description": no_risk_description, "weight": 0}

    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = i == 0
        zoom, x_tile, y_tile, px, py = latlon_to_gsi_tile_pixel(p_lat, p_lon, tile_zoom)

        img = tiles_to_fetch.get((zoom, x_tile, y_tile))
        if img is None:
            continue

        try:
            r, g, b, a = img.getpixel((px, py))
            pixel_rgb = (r, g, b)
            current_info = {"description": "情報なし", "weight": -1}

            if pixel_rgb in color_map:
                current_info = color_map[pixel_rgb]
            elif a == 0:
                current_info = {"description": no_risk_description, "weight": 0}

            if is_center_point:
                center_info = current_info

            if current_info["weight"] > max_info["weight"]:
                max_info = current_info

        except Exception as e:
            print(
                f"ERROR: Failed to process pixel at ({px}, {py}) on tile {zoom}/{x_tile}/{y_tile}. Error: {e}"
            )
            if is_center_point:
                center_info = {"description": no_risk_description, "weight": 0}

    return {
        "max_info": max_info["description"],
        "center_info": center_info["description"],
    }


def get_tsunami_inundation_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の津波浸水想定タイルから、中心点と半径100m以内の最大浸水深を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        TSUNAMI_TILE_URL,
        TSUNAMI_TILE_ZOOM,
        TSUNAMI_COLOR_MAP,
        "浸水想定なし",
        high_precision,
    )


def get_high_tide_inundation_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の高潮浸水想定タイルから、中心点と半径100m以内の最大浸水深を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        HIGH_TIDE_TILE_URL,
        HIGH_TIDE_TILE_ZOOM,
        HIGH_TIDE_COLOR_MAP,
        "浸水想定なし",
        high_precision,
    )


def get_flood_keizoku_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の浸水継続時間タイルから、中心点と半径100m以内の最大浸水継続時間を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        FLOOD_KEIZOKU_TILE_URL,
        FLOOD_KEIZOKU_TILE_ZOOM,
        FLOOD_KEIZOKU_COLOR_MAP,
        "浸水想定なし",
        high_precision,
    )


def get_kaokutoukai_hanran_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の家屋倒壊等氾濫想定区域（氾濫流）タイルから情報を取得する。
    """
    # タイル座標とピクセル座標を取得
    zoom, x_tile, y_tile, px, py = latlon_to_gsi_tile_pixel(
        lat, lon, KAOKUTOUKAI_HANRAN_TILE_ZOOM
    )

    # タイル画像を取得
    tile_url = KAOKUTOUKAI_HANRAN_TILE_URL.format(z=zoom, x=x_tile, y=y_tile)
    img = _fetch_single_tile(tile_url, HTTP_TIMEOUT_SECONDS)

    if img is None:
        return {"max_info": "判定なし", "center_info": "判定なし"}

    # ポリゴンを構築
    poly = build_polygon(img)

    # 中心点がポリゴン内に含まれるか判定
    center_info = "区域内" if is_inside(px, py, poly) else "判定なし"

    # high_precisionがTrueの場合は周辺も調査
    if high_precision:
        search_points = _get_points_in_radius(lat, lon, SEARCH_RADIUS_METERS, HIGH_PRECISION_SEARCH_POINTS)
        max_info = "判定なし"
        for p_lat, p_lon in search_points:
            _, _, _, p_px, p_py = latlon_to_gsi_tile_pixel(
                p_lat, p_lon, KAOKUTOUKAI_HANRAN_TILE_ZOOM
            )
            if is_inside(p_px, p_py, poly):
                max_info = "区域内"
                break
    else:
        max_info = center_info

    return {"max_info": max_info, "center_info": center_info}


def _format_jshis_probability(prob_value) -> str:
    """
    J-SHISから取得した確率値をフォーマットする。
    Noneの場合や解析エラーの場合は「データなし」を返す。
    """
    if prob_value is not None:
        try:
            prob_float = float(prob_value)
            return f"{math.floor(prob_float * 100)}%"
        except ValueError:
            return "データ解析失敗"
    return "データなし"


def _format_hazard_output_string(
    max_val, center_val, no_data_str: str = "データなし"
) -> str:
    """
    ハザード情報の最大値と中心点の値をフォーマットして返す。
    max_val, center_valは既にフォーマット済みの文字列、またはNone/データなし相当の値。
    """
    # max_valとcenter_valがNoneの場合を考慮
    max_val_display = max_val if max_val is not None else no_data_str
    center_val_display = center_val if center_val is not None else no_data_str

    if max_val_display == no_data_str and center_val_display == no_data_str:
        return no_data_str

    # 常に2行形式で出力
    return f" 周辺100mの最大: {max_val_display}\n 中心点: {center_val_display}"


def _get_and_format_hazard_info(
    getter_func,
    max_key: str,
    center_key: str,
    formatter_func=None,
    no_data_str: str = "データなし",
) -> str:
    """
    ハザード情報を取得し、最大値と中心点の値をフォーマットして返す汎用関数。
    getter_func: 情報を取得する関数 (例: get_jshis_info, get_inundation_depth_from_gsi_tile)
    max_key: 取得結果から最大値を取り出すためのキー
    center_key: 取得結果から中心点の値を取り出すためのキー
    formatter_func: 取得した値をさらにフォーマットする関数 (例: _format_jshis_probability)
    no_data_str: データがない場合の表示文字列
    """
    info = getter_func()
    max_val = info.get(max_key)
    center_val = info.get(center_key)

    if formatter_func:
        max_val = formatter_func(max_val)
        center_val = formatter_func(center_val)

    return _format_hazard_output_string(max_val, center_val, no_data_str)




def get_jshis_info(
    lat: float, lon: float, high_precision: bool = False
) -> dict[str, str]:
    """
    指定された緯度経度から半径100mの範囲内で最大の地震発生確率と、中心点の確率を取得する。
    J-SHIS 地点別確率値APIを使用。
    """
    results = {}
    num_search_points = HIGH_PRECISION_FALLBACK_POINTS if high_precision else STANDARD_SEARCH_POINTS
    search_points = _get_points_in_radius(lat, lon, SEARCH_RADIUS_METERS, num_search_points)

    max_prob_50 = -1.0
    max_prob_60 = -1.0
    center_prob_50 = None
    center_prob_60 = None

    # J-SHISデータを並列取得
    with ThreadPoolExecutor(max_workers=len(search_points)) as executor:
        futures = {}
        for i, (p_lat, p_lon) in enumerate(search_points):
            future = executor.submit(_fetch_jshis_data, p_lat, p_lon, HTTP_TIMEOUT_SECONDS)
            futures[i] = (future, i == 0)  # (future, is_center_point)

        # 結果を収集
        for i, (future, is_center_point) in futures.items():
            try:
                prob_50_val, prob_60_val = future.result(timeout=THREAD_TIMEOUT_SECONDS)

                if prob_50_val is not None:
                    max_prob_50 = max(max_prob_50, prob_50_val)
                    if is_center_point:
                        center_prob_50 = prob_50_val

                if prob_60_val is not None:
                    max_prob_60 = max(max_prob_60, prob_60_val)
                    if is_center_point:
                        center_prob_60 = prob_60_val

            except Exception as e:
                print(f"Error fetching J-SHIS data for point {i}: {e}")

    results["max_prob_50"] = max_prob_50 if max_prob_50 != -1.0 else None
    results["center_prob_50"] = center_prob_50
    results["max_prob_60"] = max_prob_60 if max_prob_60 != -1.0 else None
    results["center_prob_60"] = center_prob_60

    return results




def _process_flood_l2_tiles(search_points: list[tuple[float, float]]) -> tuple[dict, dict]:
    """
    想定最大浸水深（L2）タイルから情報を取得する
    """
    # 必要なタイル情報を計算し、ユニークなタイルのみを保持
    tiles_to_fetch = {}
    for p_lat, p_lon in search_points:
        zoom, x_tile, y_tile, _, _ = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)
        if (zoom, x_tile, y_tile) not in tiles_to_fetch:
            tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    # 各タイル画像を並列取得
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREAD_POOL) as executor:
        futures = {}
        for zoom, x_tile, y_tile in tiles_to_fetch.keys():
            tile_url = FLOOD_TILE_URL.format(z=zoom, x=x_tile, y=y_tile)
            future = executor.submit(_fetch_single_tile, tile_url, HTTP_TIMEOUT_SECONDS)
            futures[(zoom, x_tile, y_tile)] = future

        # 結果を収集
        for (zoom, x_tile, y_tile), future in futures.items():
            try:
                tiles_to_fetch[(zoom, x_tile, y_tile)] = future.result(timeout=THREAD_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"Error fetching flood tile {zoom}/{x_tile}/{y_tile}: {e}")
                tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    max_depth_info = {"description": "浸水なし", "weight": 0}
    center_depth_info = {"description": "浸水なし", "weight": 0}

    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = i == 0
        zoom, x_tile, y_tile, px, py = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)

        img = tiles_to_fetch.get((zoom, x_tile, y_tile))
        if img is None:
            continue

        try:
            r, g, b, a = img.getpixel((px, py))
            pixel_rgb = (r, g, b)
            current_depth_info = {"description": "情報なし", "weight": -1}

            if pixel_rgb in INUNDATION_COLOR_MAP:
                current_depth_info = INUNDATION_COLOR_MAP[pixel_rgb]
            elif a == 0:
                current_depth_info = {"description": "浸水なし", "weight": 0}

            if is_center_point:
                center_depth_info = current_depth_info

            if current_depth_info["weight"] > max_depth_info["weight"]:
                max_depth_info = current_depth_info

        except Exception as e:
            print(f"Error processing flood tile pixel: {e}")
            if is_center_point:
                center_depth_info = {"description": "処理失敗", "weight": -1}

    return max_depth_info, center_depth_info


def _process_flood_l1_tiles(search_points: list[tuple[float, float]], max_depth_info: dict, center_depth_info: dict) -> tuple[dict, dict]:
    """
    計画規模浸水深（L1）タイルから追加情報を取得する
    """
    l1_tiles_to_fetch = {}
    for p_lat, p_lon in search_points:
        zoom, x_tile, y_tile, _, _ = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)
        if (zoom, x_tile, y_tile) not in l1_tiles_to_fetch:
            l1_tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    # 計画規模タイル画像を並列取得
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREAD_POOL) as executor:
        l1_futures = {}
        for zoom, x_tile, y_tile in l1_tiles_to_fetch.keys():
            tile_url = FLOOD_L1_TILE_URL.format(z=zoom, x=x_tile, y=y_tile)
            future = executor.submit(_fetch_single_tile, tile_url, HTTP_TIMEOUT_SECONDS)
            l1_futures[(zoom, x_tile, y_tile)] = future

        # 結果を収集
        for (zoom, x_tile, y_tile), future in l1_futures.items():
            try:
                l1_tiles_to_fetch[(zoom, x_tile, y_tile)] = future.result(timeout=THREAD_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"Error fetching L1 flood tile {zoom}/{x_tile}/{y_tile}: {e}")
                l1_tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    # 計画規模タイルから浸水深を検索
    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = i == 0
        zoom, x_tile, y_tile, px, py = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)

        img = l1_tiles_to_fetch.get((zoom, x_tile, y_tile))
        if img is None:
            continue

        try:
            r, g, b, a = img.getpixel((px, py))
            pixel_rgb = (r, g, b)
            current_depth_info = {"description": "情報なし", "weight": -1}

            if pixel_rgb in INUNDATION_COLOR_MAP:
                current_depth_info = INUNDATION_COLOR_MAP[pixel_rgb]
            elif a == 0:
                current_depth_info = {"description": "浸水なし", "weight": 0}

            # 中心点の情報を更新（現在の値より良い場合）
            if is_center_point and current_depth_info["weight"] > center_depth_info["weight"]:
                center_depth_info = current_depth_info

            # 最大値を更新（現在の値より良い場合）
            if current_depth_info["weight"] > max_depth_info["weight"]:
                max_depth_info = current_depth_info

        except Exception as e:
            print(f"Error processing L1 flood tile pixel: {e}")

    return max_depth_info, center_depth_info


def get_inundation_depth_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の浸水深タイル画像から、中心点と半径100m以内の最大浸水深を取得する。
    タイルをまたがる場合も考慮する。
    """
    num_search_points = HIGH_PRECISION_FALLBACK_POINTS if high_precision else STANDARD_SEARCH_POINTS
    search_points = _get_points_in_radius(lat, lon, SEARCH_RADIUS_METERS, num_search_points)

    # L2タイル（想定最大浸水深）から情報を取得
    max_depth_info, center_depth_info = _process_flood_l2_tiles(search_points)

    # high_precision=Trueかつ結果が不十分な場合、L1タイル（計画規模）も検索
    if high_precision and max_depth_info["weight"] < 1:
        max_depth_info, center_depth_info = _process_flood_l1_tiles(
            search_points, max_depth_info, center_depth_info
        )

    return {
        "max_depth": max_depth_info["description"],
        "center_depth": center_depth_info["description"],
    }


def get_steep_slope_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の急傾斜地の崩壊警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        STEEP_SLOPE_TILE_URL,
        STEEP_SLOPE_TILE_ZOOM,
        STEEP_SLOPE_COLOR_MAP,
        "該当なし",
        high_precision,
    )


def get_debris_flow_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の土石流警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        DEBRIS_FLOW_TILE_URL,
        DEBRIS_FLOW_TILE_ZOOM,
        DEBRIS_FLOW_COLOR_MAP,
        "該当なし",
        high_precision,
    )


def get_landslide_info_from_gsi_tile(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の地すべり警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(
        lat,
        lon,
        LANDSLIDE_TILE_URL,
        LANDSLIDE_TILE_ZOOM,
        LANDSLIDE_COLOR_MAP,
        "該当なし",
        high_precision,
    )


# R-treeインデックスのキャッシュ（都道府県コード別）
_rtree_cache = {}


def _build_rtree_index(geojson_data: dict) -> tuple[index.Index, list]:
    """
    GeoJSONデータからR-treeインデックスを構築する
    """
    idx = index.Index()
    features = []

    for i, feature in enumerate(geojson_data["features"]):
        geometry = shape(feature["geometry"])
        bounds = geometry.bounds  # (minx, miny, maxx, maxy)
        idx.insert(i, bounds)
        features.append(feature)

    return idx, features


def _search_with_rtree(point: Point, rtree_idx: index.Index, features: list) -> bool:
    """
    R-treeインデックスを使って効率的に点が含まれるかを検索する
    """
    # 点の座標でR-treeから候補を絞り込み
    candidates = list(rtree_idx.intersection((point.x, point.y, point.x, point.y)))

    # 候補の中から実際に点を含むフィーチャーを探す
    for candidate_idx in candidates:
        feature = features[candidate_idx]
        if shape(feature["geometry"]).contains(point):
            return True

    return False


def _group_search_points_by_prefecture(search_points: list[tuple[float, float]]) -> tuple[dict, list]:
    """
    検索点を都道府県別にグループ化し、中心点を含む都道府県を最優先にする
    """
    pref_groups = {}
    for i, (p_lat, p_lon) in enumerate(search_points):
        pref_code = geocoding.get_pref_code(p_lat, p_lon)
        if pref_code not in pref_groups:
            pref_groups[pref_code] = []
        pref_groups[pref_code].append((i, p_lat, p_lon))

    # 中心点を最初に処理するため、中心点を含む都道府県を優先
    center_pref_code = geocoding.get_pref_code(search_points[0][0], search_points[0][1])
    pref_order = [center_pref_code] + [
        code for code in pref_groups.keys() if code != center_pref_code
    ]
    
    return pref_groups, pref_order


def _process_points_in_prefecture(
    pref_code: str, 
    points: list[tuple[int, float, float]], 
    search_points_total: int,
    max_info: dict, 
    center_info: dict
) -> tuple[dict, dict, bool]:
    """
    指定した都道府県内の検索点を処理する
    """
    pref_start_time = time.time()
    found_any = False

    # S3からGeoJSONファイルを取得
    s3_key = f"{S3_LARGE_FILL_LAND_FOLDER}/{S3_LARGE_FILL_LAND_FILE_PREFIX}{pref_code}.geojson"

    try:
        geojson_start_time = time.time()
        geojson = geojsonhelper.load_large_geojson(S3_LARGE_FILL_LAND_BUCKET, s3_key)
        geojson_load_time = time.time() - geojson_start_time
        print(f"[DEBUG] 都道府県 {pref_code}: GeoJSON読み込み時間 = {geojson_load_time:.3f}秒")

        if not geojson:
            return max_info, center_info, found_any

        # R-treeインデックスをキャッシュから取得または新規作成
        rtree_start_time = time.time()
        if pref_code not in _rtree_cache:
            rtree_idx, features = _build_rtree_index(geojson)
            _rtree_cache[pref_code] = (rtree_idx, features)
            print(f"[DEBUG] 都道府県 {pref_code}: R-treeインデックス構築完了 (features数={len(features)})")
        else:
            rtree_idx, features = _rtree_cache[pref_code]
            print(f"[DEBUG] 都道府県 {pref_code}: R-treeインデックスをキャッシュから取得")

        rtree_build_time = time.time() - rtree_start_time
        print(f"[DEBUG] 都道府県 {pref_code}: R-tree準備時間 = {rtree_build_time:.3f}秒")

        # 中心点を最初に処理するため、ポイントを並び替え
        center_points = [(i, p_lat, p_lon) for i, p_lat, p_lon in points if i == 0]
        other_points = [(i, p_lat, p_lon) for i, p_lat, p_lon in points if i != 0]
        ordered_points = center_points + other_points

        # 各ポイントをR-treeで検索
        for i, p_lat, p_lon in ordered_points:
            point_start_time = time.time()
            is_center_point = i == 0
            point = Point(p_lon, p_lat)

            current_info = {"description": "情報なし", "weight": 0}

            search_start_time = time.time()
            if _search_with_rtree(point, rtree_idx, features):
                current_info = {"description": "あり", "weight": 1}
                found_any = True
                print(f"[DEBUG] Point {i+1}/{search_points_total}: 大規模盛土造成地'あり'を発見！")
            
            search_time = time.time() - search_start_time
            print(f"[DEBUG] Point {i+1}/{search_points_total}: R-tree検索時間 = {search_time:.3f}秒")

            if is_center_point:
                center_info = current_info

            if current_info["weight"] > max_info["weight"]:
                max_info = current_info

            point_total_time = time.time() - point_start_time
            print(f"[DEBUG] Point {i+1}/{search_points_total}: 合計処理時間 = {point_total_time:.3f}秒")

            # "あり"が見つかったら即座に終了
            if found_any:
                print("[DEBUG] 早期終了: 大規模盛土造成地'あり'が見つかったため処理を終了")
                break

    except Exception as e:
        print(f"Error fetching large scale filled land info for pref {pref_code}: {e}")
        # エラーの場合、この都道府県の全ポイントを「情報なし」として処理
        for i, p_lat, p_lon in points:
            if i == 0:  # 中心点の場合
                center_info = {"description": "情報なし", "weight": 0}

    pref_total_time = time.time() - pref_start_time
    print(f"[DEBUG] 都道府県 {pref_code}: 都道府県別処理時間 = {pref_total_time:.3f}秒")
    
    return max_info, center_info, found_any


def get_large_scale_filled_land_info_from_geojson(
    lat: float, lon: float, high_precision: bool = False
) -> dict:
    """
    国土地理院の大規模盛土造成地情報をS3から取得し、中心点と半径100m以内の最大値を取得する。
    R-treeインデックスを使用して高速化。
    大規模盛土造成地は2値（あり/なし）なので、"あり"が見つかり次第早期終了する。
    """
    start_time = time.time()
    print(f"[DEBUG] get_large_scale_filled_land_info_from_geojson 開始: lat={lat}, lon={lon}, high_precision={high_precision}")

    num_search_points = HIGH_PRECISION_FALLBACK_POINTS if high_precision else STANDARD_SEARCH_POINTS
    search_points = _get_points_in_radius(lat, lon, SEARCH_RADIUS_METERS, num_search_points)

    max_info = {"description": "情報なし", "weight": 0}
    center_info = {"description": "情報なし", "weight": 0}
    found_any = False

    # 都道府県別にグループ化して処理を最適化
    pref_groups, pref_order = _group_search_points_by_prefecture(search_points)

    for pref_code in pref_order:
        if found_any:
            print(f"[DEBUG] 早期終了: 既に'あり'が見つかったため、都道府県 {pref_code} の処理をスキップ")
            break

        points = pref_groups[pref_code]
        max_info, center_info, prefecture_found = _process_points_in_prefecture(
            pref_code, points, len(search_points), max_info, center_info
        )
        
        if prefecture_found:
            found_any = True

    total_time = time.time() - start_time
    skipped_message = " (早期終了により一部処理をスキップ)" if found_any else ""
    print(f"[DEBUG] get_large_scale_filled_land_info_from_geojson 完了: 総処理時間 = {total_time:.3f}秒{skipped_message}")

    return {
        "max_info": max_info["description"],
        "center_info": center_info["description"],
    }


def get_selective_hazard_info(
    lat: float, lon: float, hazard_types: list[str] = None, high_precision: bool = False
) -> dict[str, str]:
    """
    指定されたハザード情報のみを取得する。

    Args:
        lat: 緯度
        lon: 経度
        hazard_types: 取得するハザード情報のリスト。Noneの場合は全て取得
                     - 'earthquake': 地震発生確率
                     - 'flood': 想定最大浸水深
                     - 'flood_keizoku': 浸水継続時間
                     - 'kaokutoukai_hanran': 家屋倒壊等氾濫想定区域（氾濫流）
                     - 'tsunami': 津波浸水想定
                     - 'high_tide': 高潮浸水想定
                     - 'large_fill_land': 大規模盛土造成地
                     - 'landslide': 土砂災害警戒区域
        high_precision: 高精度モード (False: 高速, True: 高精度)。デフォルトはFalse
    """
    # デフォルトで全ハザード情報を取得
    if hazard_types is None:
        hazard_types = [
            "earthquake",
            "flood",
            "flood_keizoku",
            "kaokutoukai_hanran",
            "tsunami",
            "high_tide",
            "large_fill_land",
            "landslide",
        ]

    hazard_info = {}

    # 地震発生確率情報
    if "earthquake" in hazard_types:
        jshis_info = get_jshis_info(lat, lon, high_precision)
        hazard_info["jshis_prob_50"] = {
            "max_prob": jshis_info.get("max_prob_50"),
            "center_prob": jshis_info.get("center_prob_50"),
        }
        hazard_info["jshis_prob_60"] = {
            "max_prob": jshis_info.get("max_prob_60"),
            "center_prob": jshis_info.get("center_prob_60"),
        }

    # 想定最大浸水深
    if "flood" in hazard_types:
        inundation_info = get_inundation_depth_from_gsi_tile(lat, lon, high_precision)
        hazard_info["inundation_depth"] = {
            "max_info": inundation_info.get("max_depth"),
            "center_info": inundation_info.get("center_depth"),
        }

    # 浸水継続時間
    if "flood_keizoku" in hazard_types:
        flood_keizoku_info = get_flood_keizoku_info_from_gsi_tile(lat, lon, high_precision)
        hazard_info["flood_keizoku"] = {
            "max_info": flood_keizoku_info.get("max_info"),
            "center_info": flood_keizoku_info.get("center_info"),
        }

    # 家屋倒壊等氾濫想定区域（氾濫流）
    if "kaokutoukai_hanran" in hazard_types:
        kaokutoukai_hanran_info = get_kaokutoukai_hanran_info_from_gsi_tile(lat, lon, high_precision)
        hazard_info["kaokutoukai_hanran"] = {
            "max_info": kaokutoukai_hanran_info.get("max_info"),
            "center_info": kaokutoukai_hanran_info.get("center_info"),
        }

    # 津波浸水想定
    if "tsunami" in hazard_types:
        tsunami_info = get_tsunami_inundation_info_from_gsi_tile(
            lat, lon, high_precision
        )
        hazard_info["tsunami_inundation"] = {
            "max_info": tsunami_info.get("max_info"),
            "center_info": tsunami_info.get("center_info"),
        }

    # 高潮浸水想定
    if "high_tide" in hazard_types:
        hightide_info = get_high_tide_inundation_info_from_gsi_tile(
            lat, lon, high_precision
        )
        hazard_info["hightide_inundation"] = {
            "max_info": hightide_info.get("max_info"),
            "center_info": hightide_info.get("center_info"),
        }

    # 大規模盛土造成地
    if "large_fill_land" in hazard_types:
        if ENABLE_LARGE_FILL_LAND:
            large_fill_land_info = get_large_scale_filled_land_info_from_geojson(
                lat, lon, high_precision
            )
            hazard_info["large_fill_land"] = {
                "max_info": large_fill_land_info.get("max_info"),
                "center_info": large_fill_land_info.get("center_info"),
            }
        else:
            hazard_info["large_fill_land"] = {"max_info": "無効", "center_info": "無効"}

    # 土砂災害警戒区域
    if "landslide" in hazard_types:
        debris_flow_info = get_debris_flow_info_from_gsi_tile(lat, lon, high_precision)
        steep_slope_info = get_steep_slope_info_from_gsi_tile(lat, lon, high_precision)
        landslide_info = get_landslide_info_from_gsi_tile(lat, lon, high_precision)

        hazard_info["landslide_hazard"] = {
            "debris_flow": {
                "max_info": debris_flow_info.get("max_info"),
                "center_info": debris_flow_info.get("center_info"),
            },
            "steep_slope": {
                "max_info": steep_slope_info.get("max_info"),
                "center_info": steep_slope_info.get("center_info"),
            },
            "landslide": {
                "max_info": landslide_info.get("max_info"),
                "center_info": landslide_info.get("center_info"),
            },
        }

    return hazard_info


def get_all_hazard_info(
    lat: float, lon: float, high_precision: bool = False
) -> dict[str, str]:
    """
    すべてのハザード情報をまとめて取得する（後方互換性のため）。
    """
    return get_selective_hazard_info(lat, lon, None, high_precision)


def format_all_hazard_info_for_display(hazards: dict) -> dict:
    """
    get_all_hazard_infoから返された生のハザードデータを表示用に整形する。
    """
    display_info = {}

    # 地震発生確率
    prob_50_data = hazards.get("jshis_prob_50", {})
    prob_50_str = _format_hazard_output_string(
        _format_jshis_probability(prob_50_data.get("max_prob")),
        _format_jshis_probability(prob_50_data.get("center_prob")),
    )
    display_info["30年以内に震度5強以上の地震が起こる確率"] = prob_50_str

    prob_60_data = hazards.get("jshis_prob_60", {})
    prob_60_str = _format_hazard_output_string(
        _format_jshis_probability(prob_60_data.get("max_prob")),
        _format_jshis_probability(prob_60_data.get("center_prob")),
    )
    display_info["30年以内に震度6強以上の地震が起こる確率"] = prob_60_str

    # 想定最大浸水深
    inundation_data = hazards.get("inundation_depth", {})
    display_info["想定最大浸水深"] = _format_hazard_output_string(
        inundation_data.get("max_info"),
        inundation_data.get("center_info"),
        no_data_str="浸水なし",
    )

    # 浸水継続時間
    flood_keizoku_data = hazards.get("flood_keizoku", {})
    display_info["浸水継続時間"] = _format_hazard_output_string(
        flood_keizoku_data.get("max_info"),
        flood_keizoku_data.get("center_info"),
        no_data_str="浸水想定なし",
    )

    # 津波浸水想定
    tsunami_data = hazards.get("tsunami_inundation", {})
    display_info["津波浸水想定"] = _format_hazard_output_string(
        tsunami_data.get("max_info"),
        tsunami_data.get("center_info"),
        no_data_str="浸水想定なし",
    )

    # 家屋倒壊等氾濫想定区域（氾濫流）
    kaokutoukai_hanran_data = hazards.get("kaokutoukai_hanran", {})
    display_info["家屋倒壊等氾濫想定区域（氾濫流）"] = _format_hazard_output_string(
        kaokutoukai_hanran_data.get("max_info"),
        kaokutoukai_hanran_data.get("center_info"),
        no_data_str="判定なし",
    )

    # 高潮浸水想定
    hightide_data = hazards.get("hightide_inundation", {})
    display_info["高潮浸水想定"] = _format_hazard_output_string(
        hightide_data.get("max_info"),
        hightide_data.get("center_info"),
        no_data_str="浸水想定なし",
    )

    # 大規模盛土造成地
    if ENABLE_LARGE_FILL_LAND and "large_fill_land" in hazards:
        large_fill_land_data = hazards.get("large_fill_land", {})
        display_info["大規模盛土造成地"] = _format_hazard_output_string(
            large_fill_land_data.get("max_info"),
            large_fill_land_data.get("center_info"),
            no_data_str="情報なし",
        )

    # 土砂災害警戒・特別警戒区域
    landslide_hazard_data = hazards.get("landslide_hazard", {})
    max_landslide_descriptions = []
    center_landslide_descriptions = []

    # 土石流
    debris_flow_data = landslide_hazard_data.get("debris_flow", {})
    if debris_flow_data.get("max_info") != "該当なし":
        max_landslide_descriptions.append(debris_flow_data["max_info"])
    if debris_flow_data.get("center_info") != "該当なし":
        center_landslide_descriptions.append(debris_flow_data["center_info"])

    # 急傾斜地
    steep_slope_data = landslide_hazard_data.get("steep_slope", {})
    if steep_slope_data.get("max_info") != "該当なし":
        max_landslide_descriptions.append(steep_slope_data["max_info"])
    if steep_slope_data.get("center_info") != "該当なし":
        center_landslide_descriptions.append(steep_slope_data["center_info"])

    # 地すべり
    landslide_data = landslide_hazard_data.get("landslide", {})
    if landslide_data.get("max_info") != "該当なし":
        max_landslide_descriptions.append(landslide_data["max_info"])
    if landslide_data.get("center_info") != "該当なし":
        center_landslide_descriptions.append(landslide_data["center_info"])

    max_landslide_str = (
        ", ".join(max_landslide_descriptions)
        if max_landslide_descriptions
        else "該当なし"
    )
    center_landslide_str = (
        ", ".join(center_landslide_descriptions)
        if center_landslide_descriptions
        else "該当なし"
    )

    display_info["土砂災害警戒・特別警戒区域"] = _format_hazard_output_string(
        max_landslide_str, center_landslide_str, "該当なし"
    )

    return display_info
