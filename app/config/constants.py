"""
定数定義モジュール
hazard_info.pyから分離した各種定数
"""

# 基本定数
TILE_SIZE = 256  # タイルのピクセルサイズ
SEARCH_RADIUS_METERS = 100  # 検索半径（メートル）
HIGH_PRECISION_SEARCH_POINTS = 16  # 高精度モードでの検索点数
STANDARD_SEARCH_POINTS = 4  # 標準モードでの検索点数
HTTP_TIMEOUT_SECONDS = 3  # HTTP リクエストタイムアウト
THREAD_TIMEOUT_SECONDS = 5  # スレッドタイムアウト
HIGH_PRECISION_FALLBACK_POINTS = 8  # 高精度モードでのフォールバック検索点数
MAX_WORKERS_THREAD_POOL = 4  # スレッドプール最大ワーカー数

# API エンドポイント
JSHIS_API_URL_BASE = (
    "https://www.j-shis.bosai.go.jp/map/api/pshm/Y2020/AVR/TTL_MTTL/meshinfo.geojson"
)
WMS_GETFEATUREINFO_BASE_URL = "https://disaportal.gsi.go.jp/maps/wms/hazardmap?"

# タイル設定の構造化定義
TILE_CONFIGS = {
    "flood": {
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "WATER_DEPTH_COLOR_MAP",
        "no_risk_description": "浸水なし"
    },
    "flood_l1": {
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l1_shinsuishin_newlegend_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "WATER_DEPTH_COLOR_MAP",
        "no_risk_description": "浸水なし"
    },
    "debris_flow": {
        "url": "https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "DEBRIS_FLOW_COLOR_MAP",
        "no_risk_description": "該当なし"
    },
    "steep_slope": {
        "url": "https://disaportaldata.gsi.go.jp/raster/05_kyukeishakeikaikuiki/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "STEEP_SLOPE_COLOR_MAP",
        "no_risk_description": "該当なし"
    },
    "landslide": {
        "url": "https://disaportaldata.gsi.go.jp/raster/05_jisuberikeikaikuiki/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "LANDSLIDE_COLOR_MAP",
        "no_risk_description": "該当なし"
    },
    "tsunami": {
        "url": "https://disaportaldata.gsi.go.jp/raster/04_tsunami_newlegend_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "TSUNAMI_COLOR_MAP",
        "no_risk_description": "浸水想定なし"
    },
    "high_tide": {
        "url": "https://disaportaldata.gsi.go.jp/raster/03_hightide_l2_shinsuishin_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "HIGH_TIDE_COLOR_MAP",
        "no_risk_description": "浸水想定なし"
    },
    "flood_keizoku": {
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_keizoku_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "FLOOD_KEIZOKU_COLOR_MAP",
        "no_risk_description": "浸水想定なし"
    },
    "kaokutoukai_hanran": {
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_kaokutoukai_hanran_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": None,  # 特殊処理（ポリゴン判定）
        "no_risk_description": "判定なし"
    },
    "kaokutoukai_kagan": {
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_kaokutoukai_kagan_data/{z}/{x}/{y}.png",
        "zoom": 16,
        "color_map": "KAOKUTOUKAI_KAGAN_COLOR_MAP",
        "no_risk_description": "該当なし"
    }
}

# 後方互換性のために個別定数も保持
FLOOD_TILE_URL = TILE_CONFIGS["flood"]["url"]
FLOOD_TILE_ZOOM = TILE_CONFIGS["flood"]["zoom"]
FLOOD_L1_TILE_URL = TILE_CONFIGS["flood_l1"]["url"]
DEBRIS_FLOW_TILE_URL = TILE_CONFIGS["debris_flow"]["url"]
DEBRIS_FLOW_TILE_ZOOM = TILE_CONFIGS["debris_flow"]["zoom"]
STEEP_SLOPE_TILE_URL = TILE_CONFIGS["steep_slope"]["url"]
STEEP_SLOPE_TILE_ZOOM = TILE_CONFIGS["steep_slope"]["zoom"]
LANDSLIDE_TILE_URL = TILE_CONFIGS["landslide"]["url"]
LANDSLIDE_TILE_ZOOM = TILE_CONFIGS["landslide"]["zoom"]
TSUNAMI_TILE_URL = TILE_CONFIGS["tsunami"]["url"]
TSUNAMI_TILE_ZOOM = TILE_CONFIGS["tsunami"]["zoom"]
HIGH_TIDE_TILE_URL = TILE_CONFIGS["high_tide"]["url"]
HIGH_TIDE_TILE_ZOOM = TILE_CONFIGS["high_tide"]["zoom"]
FLOOD_KEIZOKU_TILE_URL = TILE_CONFIGS["flood_keizoku"]["url"]
FLOOD_KEIZOKU_TILE_ZOOM = TILE_CONFIGS["flood_keizoku"]["zoom"]
KAOKUTOUKAI_HANRAN_TILE_URL = TILE_CONFIGS["kaokutoukai_hanran"]["url"]
KAOKUTOUKAI_HANRAN_TILE_ZOOM = TILE_CONFIGS["kaokutoukai_hanran"]["zoom"]
KAOKUTOUKAI_KAGAN_TILE_URL = TILE_CONFIGS["kaokutoukai_kagan"]["url"]
KAOKUTOUKAI_KAGAN_TILE_ZOOM = TILE_CONFIGS["kaokutoukai_kagan"]["zoom"]