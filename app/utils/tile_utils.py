"""
タイル処理ユーティリティモジュール
座標変換、タイル取得、空間検索などの共通処理
"""
import math
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from app.config.constants import (
    TILE_SIZE, 
    SEARCH_RADIUS_METERS, 
    STANDARD_SEARCH_POINTS,
    HTTP_TIMEOUT_SECONDS,
    THREAD_TIMEOUT_SECONDS,
    MAX_WORKERS_THREAD_POOL
)


def latlon_to_gsi_tile_pixel(
    lat: float, lon: float, zoom: int
) -> tuple[int, int, int, int, int]:
    """
    緯度経度とズームレベルから地理院タイル座標(Z, X, Y)とタイル内ピクセル座標(px, py)を計算する。
    """
    n = 2**zoom
    lat_rad = math.radians(lat)

    x_tile = int(n * ((lon + 180) / 360))
    y_tile = int(
        n * (1 - (math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)) / 2
    )

    # タイル内ピクセル座標 (0-255)
    px = int(TILE_SIZE * (n * ((lon + 180) / 360) - x_tile))
    py = int(
        TILE_SIZE
        * (
            n
            * (1 - (math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi))
            / 2
            - y_tile
        )
    )

    return zoom, x_tile, y_tile, px, py


def fetch_single_tile(tile_url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> Image.Image | None:
    """
    単一のタイル画像を取得するヘルパー関数
    """
    try:
        response = requests.get(tile_url, timeout=timeout)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tile {tile_url}: {e}")
        return None


def get_points_in_radius(
    lat: float, lon: float, radius_m: int, num_points: int = STANDARD_SEARCH_POINTS
) -> list[tuple[float, float]]:
    """
    指定した中心座標から半径radius_mの円周上の点をnum_points個生成する。
    デフォルトは4点（北東南西）でパフォーマンスと精度のバランスを最適化。
    """
    points = [(lat, lon)]  # 中心点を常に含める
    R = 6378137  # 地球の半径(m)

    # 4点の場合は主要4方向（北東南西）に配置
    if num_points == STANDARD_SEARCH_POINTS:
        directions = [0, math.pi / 2, math.pi, 3 * math.pi / 2]  # 北、東、南、西
        for angle in directions:
            d_lat = radius_m * math.cos(angle)
            d_lon = radius_m * math.sin(angle)

            new_lat = lat + (d_lat / R) * (180 / math.pi)
            new_lon = lon + (d_lon / R) * (180 / math.pi) / math.cos(
                lat * math.pi / 180
            )

            points.append((new_lat, new_lon))
    else:
        # その他の点数の場合は等間隔配置
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points

            d_lat = radius_m * math.cos(angle)
            d_lon = radius_m * math.sin(angle)

            new_lat = lat + (d_lat / R) * (180 / math.pi)
            new_lon = lon + (d_lon / R) * (180 / math.pi) / math.cos(
                lat * math.pi / 180
            )

            points.append((new_lat, new_lon))

    return points


def fetch_tiles_parallel(tile_urls: dict[tuple, str]) -> dict[tuple, Image.Image | None]:
    """
    複数のタイルを並列取得する
    
    Args:
        tile_urls: {(zoom, x_tile, y_tile): tile_url} の辞書
        
    Returns:
        dict: {(zoom, x_tile, y_tile): Image.Image | None} の辞書
    """
    tiles = {key: None for key in tile_urls.keys()}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREAD_POOL) as executor:
        futures = {}
        for coords, tile_url in tile_urls.items():
            future = executor.submit(fetch_single_tile, tile_url, HTTP_TIMEOUT_SECONDS)
            futures[coords] = future

        # 結果を収集
        for coords, future in futures.items():
            try:
                tiles[coords] = future.result(timeout=THREAD_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"Error fetching tile {coords}: {e}")
                tiles[coords] = None
    
    return tiles