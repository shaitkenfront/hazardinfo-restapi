"""
色マップ定義モジュール
各種ハザード情報の色と説明・重み値の対応マップ
"""

# 共通浸水深色マップ（洪水、津波、高潮で共通利用）
WATER_DEPTH_COLOR_MAP = {
    (220, 122, 220): {"description": "20m以上", "weight": 20},
    (242, 133, 201): {"description": "10m以上20m未満", "weight": 10},
    (255, 145, 145): {"description": "5m以上10m未満", "weight": 5},
    (255, 183, 183): {"description": "3m以上5m未満", "weight": 3},
    (255, 216, 192): {"description": "0.5m以上3m未満", "weight": 1.0},
    (248, 225, 166): {"description": "0.5m以上1m未満", "weight": 0.5},
    (247, 245, 169): {"description": "0.5m未満", "weight": 0.4},
    (255, 255, 179): {"description": "0.3m未満", "weight": 0.2},
}

# 後方互換性のために旧名称もエイリアスとして保持
INUNDATION_COLOR_MAP = WATER_DEPTH_COLOR_MAP
TSUNAMI_COLOR_MAP = WATER_DEPTH_COLOR_MAP
HIGH_TIDE_COLOR_MAP = WATER_DEPTH_COLOR_MAP
FLOOD_INUNDATION_COLOR_MAP = WATER_DEPTH_COLOR_MAP

# 土石流警戒区域・特別警戒区域タイルの色マップ
DEBRIS_FLOW_COLOR_MAP = {
    (165, 0, 33): {"description": "土石流(特別警戒)", "weight": 2},
    (230, 200, 50): {"description": "土石流", "weight": 1},
}

# 急傾斜地の崩壊警戒区域タイルの色マップ
STEEP_SLOPE_COLOR_MAP = {
    (250, 40, 0): {"description": "急傾斜地(特別警戒)", "weight": 2},
    (250, 230, 0): {"description": "急傾斜地", "weight": 1},
}

# 地すべり警戒区域タイルの色マップ
LANDSLIDE_COLOR_MAP = {
    (180, 0, 40): {"description": "地すべり(特別警戒)", "weight": 2},
    (255, 153, 0): {"description": "地すべり", "weight": 1},
}

# 浸水継続時間タイルの色と時間の対応マップ
FLOOD_KEIZOKU_COLOR_MAP = {
    (96, 0, 96): {"description": "4週間以上～", "weight": 28},
    (180, 0, 104): {"description": "2週間以上～", "weight": 21},
    (255, 40, 0): {"description": "1週間～2週間未満", "weight": 14},
    (255, 153, 0): {"description": "3日～1週間未満", "weight": 7},
    (250, 245, 0): {"description": "1日～3日未満", "weight": 3},
    (0, 65, 255): {"description": "12時間～1日未満", "weight": 1},
    (160, 210, 255): {"description": "12時間未満", "weight": 0.5},
}

# 家屋倒壊等氾濫想定区域（河岸侵食）タイルの色マップ
# このタイプは色の有無で判定（色があれば「該当あり」、透明であれば「該当なし」）
KAOKUTOUKAI_KAGAN_COLOR_MAP = {}


def get_color_map_by_name(name: str) -> dict:
    """
    色マップ名から対応する色マップを取得する
    
    Args:
        name: 色マップ名
        
    Returns:
        dict: 色マップ辞書
        
    Raises:
        ValueError: 存在しない色マップ名が指定された場合
    """
    color_maps = {
        "WATER_DEPTH_COLOR_MAP": WATER_DEPTH_COLOR_MAP,
        "INUNDATION_COLOR_MAP": INUNDATION_COLOR_MAP,
        "TSUNAMI_COLOR_MAP": TSUNAMI_COLOR_MAP,
        "HIGH_TIDE_COLOR_MAP": HIGH_TIDE_COLOR_MAP,
        "FLOOD_INUNDATION_COLOR_MAP": FLOOD_INUNDATION_COLOR_MAP,
        "DEBRIS_FLOW_COLOR_MAP": DEBRIS_FLOW_COLOR_MAP,
        "STEEP_SLOPE_COLOR_MAP": STEEP_SLOPE_COLOR_MAP,
        "LANDSLIDE_COLOR_MAP": LANDSLIDE_COLOR_MAP,
        "FLOOD_KEIZOKU_COLOR_MAP": FLOOD_KEIZOKU_COLOR_MAP,
        "KAOKUTOUKAI_KAGAN_COLOR_MAP": KAOKUTOUKAI_KAGAN_COLOR_MAP,
    }
    
    if name not in color_maps:
        raise ValueError(f"Unknown color map: {name}")
    
    return color_maps[name]