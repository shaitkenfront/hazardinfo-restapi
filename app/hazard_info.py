import requests
import json
import math
from PIL import Image
from io import BytesIO
from shapely.geometry import shape, Point
from concurrent.futures import ThreadPoolExecutor
from app import geocoding, geojsonhelper

# J-SHIS API 地点別確率値APIのベースURL (2020年版、平均、全期間)
JSHIS_API_URL_BASE = "https://www.j-shis.bosai.go.jp/map/api/pshm/Y2020/AVR/TTL_MTTL/meshinfo.geojson"

# 国土地理院WMS GetFeatureInfo エンドポイント
WMS_GETFEATUREINFO_BASE_URL = "https://disaportal.gsi.go.jp/maps/wms/hazardmap?"

# 想定最大浸水深タイルURL
FLOOD_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png"
FLOOD_TILE_ZOOM = 17 # ズームレベル固定

# 土石流警戒区域・特別警戒区域URL
DEBRIS_FLOW_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png"
DEBRIS_FLOW_TILE_ZOOM = 17 # ズームレベル固定

# 急傾斜地の崩壊警戒区域URL
STEEP_SLOPE_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/05_kyukeishakeikaikuiki/{z}/{x}/{y}.png"
STEEP_SLOPE_TILE_ZOOM = 17 # ズームレベル固定

# 地すべり警戒区域タイルURL
LANDSLIDE_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/05_jisuberikeikaikuiki/{z}/{x}/{y}.png"
LANDSLIDE_TILE_ZOOM = 17 # ズームレベル固定

# 津波浸水想定タイルURL
TSUNAMI_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/04_tsunami_newlegend_data/{z}/{x}/{y}.png"
TSUNAMI_TILE_ZOOM = 17 # ズームレベル固定

# 高潮浸水想定タイルURL
HIGH_TIDE_TILE_URL = "https://disaportaldata.gsi.go.jp/raster/03_hightide_l2_shinsuishin_data/{z}/{x}/{y}.png"
HIGH_TIDE_TILE_ZOOM = 17 # ズームレベル固定

# 大規模盛土造成地
S3_LARGE_FILL_LAND_BUCKET = "linebot-hazardinfo-storage-2be2654c-2c7c-001f-a2e7-fadd69e05d62"
S3_LARGE_FILL_LAND_FOLDER = "A54-23_GEOJSON"
S3_LARGE_FILL_LAND_FILE_PREFIX = "A54-23_"


# 浸水深タイルの色と浸水深の対応マップ
INUNDATION_COLOR_MAP = {
    (220,122,220): {"description": "20m以上", "weight": 20},
    (242,133,201): {"description": "10m以上20m未満", "weight": 10},
    (255,145,145): {"description": "5m以上10m未満", "weight": 5},
    (255,183,183): {"description": "3m以上5m未満", "weight": 3},
    (255,216,192): {"description": "0.5m以上3m未満", "weight": 1.0},
    (248,225,166): {"description": "0.5m以上1m未満", "weight": 0.5},
    (247,245,169): {"description": "0.5m未満", "weight": 0.4},
    (255,255,179): {"description": "0.3m未満", "weight": 0.2}
}

# 土石流警戒区域・特別警戒区域タイルの色と浸水深の対応マップ
DEBRIS_FLOW_COLOR_MAP = {
    (165, 0, 33): {"description": "土石流(特別警戒)", "weight": 2},
    (230, 200, 50): {"description": "土石流", "weight": 1}
}

# 急傾斜地の崩壊警戒区域タイルの色と浸水深の対応マップ
STEEP_SLOPE_COLOR_MAP = {
    (250, 40, 0): {"description": "急傾斜地(特別警戒)", "weight": 2},
    (250, 230, 0): {"description": "急傾斜地", "weight": 1}
}

# 地すべり警戒区域タイルの色と浸水深の対応マップ
LANDSLIDE_COLOR_MAP = {
    (180, 0, 40): {"description": "地すべり(特別警戒)", "weight": 2},
    (255, 153, 0): {"description": "地すべり", "weight": 1}
}

# 津波浸水想定タイルの色と浸水深の対応マップ
TSUNAMI_COLOR_MAP = {
    (220, 122, 220): {"description": "20m以上", "weight": 20},
    (242, 133, 201): {"description": "10m以上20m未満", "weight": 10},
    (255, 145, 145): {"description": "5m以上10m未満", "weight": 5},
    (255, 183, 183): {"description": "3m以上5m未満", "weight": 3},
    (255, 216, 192): {"description": "0.5m以上3m未満", "weight": 1.0},
    (248, 225, 166): {"description": "0.5m以上1m未満", "weight": 0.5},
    (247, 245, 169): {"description": "0.5m未満", "weight": 0.4},
    (255, 255, 179): {"description": "0.3m未満", "weight": 0.2}
}

# 高潮浸水想定タイルの色と浸水深の対応マップ
HIGH_TIDE_COLOR_MAP = {
    (220, 122, 220): {"description": "20m以上", "weight": 20},
    (242, 133, 201): {"description": "10m以上20m未満", "weight": 10},
    (255, 145, 145): {"description": "5m以上10m未満", "weight": 5},
    (255, 183, 183): {"description": "3m以上5m未満", "weight": 3},
    (255, 216, 192): {"description": "0.5m以上3m未満", "weight": 1.0},
    (248, 225, 166): {"description": "0.5m以上1m未満", "weight": 0.5},
    (247, 245, 169): {"description": "0.5m未満", "weight": 0.4},
    (255, 255, 179): {"description": "0.3m未満", "weight": 0.2}
}

# 洪水浸水想定区域タイルの色と浸水深の対応マップ
FLOOD_INUNDATION_COLOR_MAP = {
    (220, 122, 220): {"description": "20m以上", "weight": 20},
    (242, 133, 201): {"description": "10m以上20m未満", "weight": 10},
    (255, 145, 145): {"description": "5m以上10m未満", "weight": 5},
    (255, 183, 183): {"description": "3m以上5m未満", "weight": 3},
    (255, 216, 192): {"description": "0.5m以上3m未満", "weight": 1.0},
    (248, 225, 166): {"description": "0.5m以上1m未満", "weight": 0.5},
    (247, 245, 169): {"description": "0.5m未満", "weight": 0.4},
    (255, 255, 179): {"description": "0.3m未満", "weight": 0.2}
}

def _fetch_single_tile(tile_url: str, timeout: int = 3) -> Image.Image | None:
    """
    単一のタイル画像を取得するヘルパー関数
    """
    try:
        response = requests.get(tile_url, timeout=timeout)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert('RGBA')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tile {tile_url}: {e}")
        return None

def _fetch_jshis_data(lat: float, lon: float, timeout: int = 3) -> tuple[float | None, float | None]:
    """
    単一の地点のJ-SHISデータを取得するヘルパー関数
    """
    params_50 = {
        'position': f'{lon},{lat}',
        'epsg': 4326,
    }
    params_60 = {
        'position': f'{lon},{lat}',
        'epsg': 4326,
    }
    
    prob_50 = None
    prob_60 = None
    
    try:
        response_50 = requests.get(JSHIS_API_URL_BASE, params=params_50, timeout=timeout)
        response_50.raise_for_status()
        geojson_50 = response_50.json()
        
        if geojson_50.get('features') and geojson_50['features'][0].get('properties'):
            prob_50_val = geojson_50['features'][0]['properties'].get('T30_I50_PS')
            if prob_50_val is not None:
                prob_50 = float(prob_50_val)
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching J-SHIS 50 data for {lat},{lon}: {e}")

    try:
        response_60 = requests.get(JSHIS_API_URL_BASE, params=params_60, timeout=timeout)
        response_60.raise_for_status()
        geojson_60 = response_60.json()
        
        if geojson_60.get('features') and geojson_60['features'][0].get('properties'):
            prob_60_val = geojson_60['features'][0]['properties'].get('T30_I60_PS')
            if prob_60_val is not None:
                prob_60 = float(prob_60_val)
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching J-SHIS 60 data for {lat},{lon}: {e}")
    
    return prob_50, prob_60

def _get_max_info_from_tile(lat: float, lon: float, tile_url_template: str, tile_zoom: int, color_map: dict, no_risk_description: str, num_search_points: int = 4) -> dict:
    """
    指定されたタイルソースから、中心点と半径100m以内の最大値を取得する汎用関数。
    タイルをまたがる場合も考慮する。
    """
    search_points = _get_points_in_radius(lat, lon, 100, num_search_points)
    
    tiles_to_fetch = {}
    for p_lat, p_lon in search_points:
        zoom, x_tile, y_tile, _, _ = latlon_to_gsi_tile_pixel(p_lat, p_lon, tile_zoom)
        if (zoom, x_tile, y_tile) not in tiles_to_fetch:
            tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    # タイルを並列取得
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for (zoom, x_tile, y_tile) in tiles_to_fetch.keys():
            tile_url = tile_url_template.format(z=zoom, x=x_tile, y=y_tile)
            future = executor.submit(_fetch_single_tile, tile_url, 3)
            futures[(zoom, x_tile, y_tile)] = future
        
        # 結果を収集
        for (zoom, x_tile, y_tile), future in futures.items():
            try:
                tiles_to_fetch[(zoom, x_tile, y_tile)] = future.result(timeout=5)
            except Exception as e:
                print(f"Error fetching tile {zoom}/{x_tile}/{y_tile}: {e}")
                tiles_to_fetch[(zoom, x_tile, y_tile)] = None

    max_info = {"description": no_risk_description, "weight": 0}
    center_info = {"description": no_risk_description, "weight": 0}

    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = (i == 0)
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
            print(f"ERROR: Failed to process pixel at ({px}, {py}) on tile {zoom}/{x_tile}/{y_tile}. Error: {e}")
            if is_center_point:
                center_info = {"description": "処理失敗", "weight": -1}

    return {"max_info": max_info["description"], "center_info": center_info["description"]}

def get_tsunami_inundation_info_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の津波浸水想定タイルから、中心点と半径100m以内の最大浸水深を取得する。
    """
    return _get_max_info_from_tile(lat, lon, TSUNAMI_TILE_URL, TSUNAMI_TILE_ZOOM, TSUNAMI_COLOR_MAP, "浸水想定なし", num_search_points)

def get_high_tide_inundation_info_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の高潮浸水想定タイルから、中心点と半径100m以内の最大浸水深を取得する。
    """
    return _get_max_info_from_tile(lat, lon, HIGH_TIDE_TILE_URL, HIGH_TIDE_TILE_ZOOM, HIGH_TIDE_COLOR_MAP, "浸水想定なし", num_search_points)

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
            return 'データ解析失敗'
    return 'データなし'

def _format_hazard_output_string(max_val, center_val, no_data_str: str = 'データなし') -> str:
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

def _get_and_format_hazard_info(getter_func, max_key: str, center_key: str, formatter_func=None, no_data_str: str = 'データなし') -> str:
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



def _get_points_in_radius(lat: float, lon: float, radius_m: int, num_points: int = 4) -> list[tuple[float, float]]:
    """
    指定した中心座標から半径radius_mの円周上の点をnum_points個生成する。
    デフォルトは4点（北東南西）でパフォーマンスと精度のバランスを最適化。
    """
    points = [(lat, lon)] # 中心点を常に含める
    R = 6378137  # 地球の半径(m)
    
    # 4点の場合は主要4方向（北東南西）に配置
    if num_points == 4:
        directions = [0, math.pi/2, math.pi, 3*math.pi/2]  # 北、東、南、西
        for angle in directions:
            d_lat = radius_m * math.cos(angle)
            d_lon = radius_m * math.sin(angle)
            
            new_lat = lat + (d_lat / R) * (180 / math.pi)
            new_lon = lon + (d_lon / R) * (180 / math.pi) / math.cos(lat * math.pi / 180)
            
            points.append((new_lat, new_lon))
    else:
        # その他の点数の場合は等間隔配置
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            
            d_lat = radius_m * math.cos(angle)
            d_lon = radius_m * math.sin(angle)
            
            new_lat = lat + (d_lat / R) * (180 / math.pi)
            new_lon = lon + (d_lon / R) * (180 / math.pi) / math.cos(lat * math.pi / 180)
            
            points.append((new_lat, new_lon))
        
    return points

def get_jshis_info(lat: float, lon: float, num_search_points: int = 4) -> dict[str, str]:
    """
    指定された緯度経度から半径100mの範囲内で最大の地震発生確率と、中心点の確率を取得する。
    J-SHIS 地点別確率値APIを使用。
    """
    results = {}
    search_points = _get_points_in_radius(lat, lon, 100, num_search_points)
    
    max_prob_50 = -1.0
    max_prob_60 = -1.0
    center_prob_50 = None
    center_prob_60 = None

    # J-SHISデータを並列取得
    with ThreadPoolExecutor(max_workers=len(search_points)) as executor:
        futures = {}
        for i, (p_lat, p_lon) in enumerate(search_points):
            future = executor.submit(_fetch_jshis_data, p_lat, p_lon, 3)
            futures[i] = (future, i == 0)  # (future, is_center_point)
        
        # 結果を収集
        for i, (future, is_center_point) in futures.items():
            try:
                prob_50_val, prob_60_val = future.result(timeout=5)
                
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

    results['max_prob_50'] = max_prob_50 if max_prob_50 != -1.0 else None
    results['center_prob_50'] = center_prob_50
    results['max_prob_60'] = max_prob_60 if max_prob_60 != -1.0 else None
    results['center_prob_60'] = center_prob_60

    return results

def latlon_to_gsi_tile_pixel(lat: float, lon: float, zoom: int) -> tuple[int, int, int, int, int]:
    """
    緯度経度とズームレベルから地理院タイル座標(Z, X, Y)とタイル内ピクセル座標(px, py)を計算する。
    """
    n = 2 ** zoom
    lon_rad = math.radians(lon)
    lat_rad = math.radians(lat)

    x_tile = int(n * ((lon + 180) / 360))
    y_tile = int(n * (1 - (math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)) / 2)

    # タイル内ピクセル座標 (0-255)
    px = int(256 * (n * ((lon + 180) / 360) - x_tile))
    py = int(256 * (n * (1 - (math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)) / 2 - y_tile))

    return zoom, x_tile, y_tile, px, py

def get_inundation_depth_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の浸水深タイル画像から、中心点と半径100m以内の最大浸水深を取得する。
    タイルをまたがる場合も考慮する。
    """
    search_points = _get_points_in_radius(lat, lon, 100, num_search_points)
    
    # 必要なタイル情報を計算し、ユニークなタイルのみを保持
    tiles_to_fetch = {}
    for p_lat, p_lon in search_points:
        zoom, x_tile, y_tile, _, _ = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)
        if (zoom, x_tile, y_tile) not in tiles_to_fetch:
            tiles_to_fetch[(zoom, x_tile, y_tile)] = None # 初期値はNone

    # 各タイル画像を並列取得
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for (zoom, x_tile, y_tile) in tiles_to_fetch.keys():
            tile_url = FLOOD_TILE_URL.format(z=zoom, x=x_tile, y=y_tile)
            future = executor.submit(_fetch_single_tile, tile_url, 3)
            futures[(zoom, x_tile, y_tile)] = future
        
        # 結果を収集
        for (zoom, x_tile, y_tile), future in futures.items():
            try:
                tiles_to_fetch[(zoom, x_tile, y_tile)] = future.result(timeout=5)
            except Exception as e:
                print(f"Error fetching flood tile {zoom}/{x_tile}/{y_tile}: {e}")
                tiles_to_fetch[(zoom, x_tile, y_tile)] = None
    
    max_depth_info = {"description": "浸水なし", "weight": 0}
    center_depth_info = {"description": "浸水なし", "weight": 0}

    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = (i == 0)
        zoom, x_tile, y_tile, px, py = latlon_to_gsi_tile_pixel(p_lat, p_lon, FLOOD_TILE_ZOOM)
        
        img = tiles_to_fetch.get((zoom, x_tile, y_tile))
        if img is None:
            continue # タイル取得に失敗した場合はスキップ

        try:
            r, g, b, a = img.getpixel((px, py))
            pixel_rgb = (r, g, b)
            current_depth_info = {"description": "情報なし", "weight": -1} # デフォルト値

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

    return {"max_depth": max_depth_info["description"], "center_depth": center_depth_info["description"]}

def get_steep_slope_info_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の急傾斜地の崩壊警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(lat, lon, STEEP_SLOPE_TILE_URL, STEEP_SLOPE_TILE_ZOOM, STEEP_SLOPE_COLOR_MAP, "該当なし", num_search_points)

def get_debris_flow_info_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の土石流警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(lat, lon, DEBRIS_FLOW_TILE_URL, DEBRIS_FLOW_TILE_ZOOM, DEBRIS_FLOW_COLOR_MAP, "該当なし", num_search_points)

def get_landslide_info_from_gsi_tile(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の地すべり警戒区域タイルから情報を取得する。
    """
    return _get_max_info_from_tile(lat, lon, LANDSLIDE_TILE_URL, LANDSLIDE_TILE_ZOOM, LANDSLIDE_COLOR_MAP, "該当なし", num_search_points)
    
def get_large_scale_filled_land_info_from_geojson(lat: float, lon: float, num_search_points: int = 4) -> dict:
    """
    国土地理院の大規模盛土造成地情報をS3から取得し、中心点と半径100m以内の最大値を取得する。
    """
    search_points = _get_points_in_radius(lat, lon, 100, num_search_points)

    max_info = {"description": "情報なし", "weight": 0}
    center_info = {"description": "情報なし", "weight": 0}

    for i, (p_lat, p_lon) in enumerate(search_points):
        is_center_point = (i == 0)
        
        # 緯度経度から都道府県番号を計算
        pref_code = geocoding.get_pref_code(p_lat, p_lon)
        point = Point(p_lon, p_lat)

        # S3からGeoJSONファイルを取得
        s3_key = f"{S3_LARGE_FILL_LAND_FOLDER}/{S3_LARGE_FILL_LAND_FILE_PREFIX}{pref_code}.geojson"
        
        current_info = {"description": "情報なし", "weight": 0}
        try:
            geojson = geojsonhelper.load_large_geojson(S3_LARGE_FILL_LAND_BUCKET, s3_key)
            if geojson:
                for feature in geojson["features"]:
                    if shape(feature["geometry"]).contains(point):
                        current_info = {"description": "あり", "weight": 1}
                        break
        except Exception as e:
            print(f"Error fetching large scale filled land info for point ({p_lat}, {p_lon}): {e}")
            if is_center_point:
                center_info = {"description": "処理失敗", "weight": -1}
                
        if is_center_point:
            center_info = current_info

        if current_info["weight"] > max_info["weight"]:
            max_info = current_info

    return {"max_info": max_info["description"], "center_info": center_info["description"]}

def get_selective_hazard_info(lat: float, lon: float, hazard_types: list[str] = None, search_points: int = 4) -> dict[str, str]:
    """
    指定されたハザード情報のみを取得する。
    
    Args:
        lat: 緯度
        lon: 経度  
        hazard_types: 取得するハザード情報のリスト。Noneの場合は全て取得
                     - 'earthquake': 地震発生確率
                     - 'flood': 想定最大浸水深
                     - 'tsunami': 津波浸水想定
                     - 'high_tide': 高潮浸水想定
                     - 'large_fill_land': 大規模盛土造成地
                     - 'landslide': 土砂災害警戒区域
        search_points: 検索点数 (4: 高速, 8: 高精度)。デフォルトは4
    """
    # デフォルトで全ハザード情報を取得
    if hazard_types is None:
        hazard_types = ['earthquake', 'flood', 'tsunami', 'high_tide', 'large_fill_land', 'landslide']
    
    hazard_info = {}

    # 地震発生確率情報
    if 'earthquake' in hazard_types:
        jshis_info = get_jshis_info(lat, lon, search_points)
        hazard_info['jshis_prob_50'] = {
            'max_prob': jshis_info.get('max_prob_50'),
            'center_prob': jshis_info.get('center_prob_50')
        }
        hazard_info['jshis_prob_60'] = {
            'max_prob': jshis_info.get('max_prob_60'),
            'center_prob': jshis_info.get('center_prob_60')
        }
    
    # 想定最大浸水深
    if 'flood' in hazard_types:
        inundation_info = get_inundation_depth_from_gsi_tile(lat, lon, search_points)
        hazard_info['inundation_depth'] = {
            'max_info': inundation_info.get('max_depth'),
            'center_info': inundation_info.get('center_depth')
        }

    # 津波浸水想定
    if 'tsunami' in hazard_types:
        tsunami_info = get_tsunami_inundation_info_from_gsi_tile(lat, lon, search_points)
        hazard_info['tsunami_inundation'] = {
            'max_info': tsunami_info.get('max_info'),
            'center_info': tsunami_info.get('center_info')
        }

    # 高潮浸水想定
    if 'high_tide' in hazard_types:
        hightide_info = get_high_tide_inundation_info_from_gsi_tile(lat, lon, search_points)
        hazard_info['hightide_inundation'] = {
            'max_info': hightide_info.get('max_info'),
            'center_info': hightide_info.get('center_info')
        }

    # 大規模盛土造成地
    if 'large_fill_land' in hazard_types:
        large_fill_land_info = get_large_scale_filled_land_info_from_geojson(lat, lon, search_points)
        hazard_info['large_fill_land'] = {
            'max_info': large_fill_land_info.get('max_info'),
            'center_info': large_fill_land_info.get('center_info')
        }
    
    # 土砂災害警戒区域
    if 'landslide' in hazard_types:
        debris_flow_info = get_debris_flow_info_from_gsi_tile(lat, lon, search_points)
        steep_slope_info = get_steep_slope_info_from_gsi_tile(lat, lon, search_points)
        landslide_info = get_landslide_info_from_gsi_tile(lat, lon, search_points)

        hazard_info['landslide_hazard'] = {
            'debris_flow': {'max_info': debris_flow_info.get('max_info'), 'center_info': debris_flow_info.get('center_info')},
            'steep_slope': {'max_info': steep_slope_info.get('max_info'), 'center_info': steep_slope_info.get('center_info')},
            'landslide': {'max_info': landslide_info.get('max_info'), 'center_info': landslide_info.get('center_info')}
        }

    return hazard_info

def get_all_hazard_info(lat: float, lon: float, search_points: int = 4) -> dict[str, str]:
    """
    すべてのハザード情報をまとめて取得する（後方互換性のため）。
    """
    return get_selective_hazard_info(lat, lon, None, search_points)

def format_all_hazard_info_for_display(hazards: dict) -> dict:
    """
    get_all_hazard_infoから返された生のハザードデータを表示用に整形する。
    """
    display_info = {}

    # 地震発生確率
    prob_50_data = hazards.get('jshis_prob_50', {})
    prob_50_str = _format_hazard_output_string(
        _format_jshis_probability(prob_50_data.get('max_prob')),
        _format_jshis_probability(prob_50_data.get('center_prob'))
    )
    display_info['30年以内に震度5強以上の地震が起こる確率'] = prob_50_str

    prob_60_data = hazards.get('jshis_prob_60', {})
    prob_60_str = _format_hazard_output_string(
        _format_jshis_probability(prob_60_data.get('max_prob')),
        _format_jshis_probability(prob_60_data.get('center_prob'))
    )
    display_info['30年以内に震度6強以上の地震が起こる確率'] = prob_60_str

    # 想定最大浸水深
    inundation_data = hazards.get('inundation_depth', {})
    display_info['想定最大浸水深'] = _format_hazard_output_string(
        inundation_data.get('max_info'),
        inundation_data.get('center_info'),
        no_data_str="浸水なし"
    )

    # 津波浸水想定
    tsunami_data = hazards.get('tsunami_inundation', {})
    display_info['津波浸水想定'] = _format_hazard_output_string(
        tsunami_data.get('max_info'),
        tsunami_data.get('center_info'),
        no_data_str="浸水想定なし"
    )

    # 高潮浸水想定
    hightide_data = hazards.get('hightide_inundation', {})
    display_info['高潮浸水想定'] = _format_hazard_output_string(
        hightide_data.get('max_info'),
        hightide_data.get('center_info'),
        no_data_str="浸水想定なし"
    )

    # 大規模盛土造成地
    large_fill_land_data = hazards.get('large_fill_land', {})
    display_info['大規模盛土造成地'] = _format_hazard_output_string(
        large_fill_land_data.get('max_info'),
        large_fill_land_data.get('center_info'),
        no_data_str="情報なし"
    )

    # 土砂災害警戒・特別警戒区域
    landslide_hazard_data = hazards.get('landslide_hazard', {})
    max_landslide_descriptions = []
    center_landslide_descriptions = []

    # 土石流
    debris_flow_data = landslide_hazard_data.get('debris_flow', {})
    if debris_flow_data.get('max_info') != '該当なし':
        max_landslide_descriptions.append(debris_flow_data['max_info'])
    if debris_flow_data.get('center_info') != '該当なし':
        center_landslide_descriptions.append(debris_flow_data['center_info'])

    # 急傾斜地
    steep_slope_data = landslide_hazard_data.get('steep_slope', {})
    if steep_slope_data.get('max_info') != '該当なし':
        max_landslide_descriptions.append(steep_slope_data['max_info'])
    if steep_slope_data.get('center_info') != '該当なし':
        center_landslide_descriptions.append(steep_slope_data['center_info'])

    # 地すべり
    landslide_data = landslide_hazard_data.get('landslide', {})
    if landslide_data.get('max_info') != '該当なし':
        max_landslide_descriptions.append(landslide_data['max_info'])
    if landslide_data.get('center_info') != '該当なし':
        center_landslide_descriptions.append(landslide_data['center_info'])

    max_landslide_str = ", ".join(max_landslide_descriptions) if max_landslide_descriptions else "該当なし"
    center_landslide_str = ", ".join(center_landslide_descriptions) if center_landslide_descriptions else "該当なし"

    display_info['土砂災害警戒・特別警戒区域'] = _format_hazard_output_string(max_landslide_str, center_landslide_str, "該当なし")

    return display_info
