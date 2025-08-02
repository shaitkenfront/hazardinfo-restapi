import re

# 緯度経度の正規表現パターン（例: 35.6586, 139.7454）
LATLON_PATTERN = re.compile(r'^\s*(-?\d{1,2}(\.\d+)?)\s*,\s*(-?\d{1,3}(\.\d+)?)\s*$')

def parse_input_type(text: str) -> tuple[str, str]:
    """
    ユーザーの入力テキストを解析し、タイプと値を返す。

    Args:
        text: ユーザーからの入力文字列。

    Returns:
        (str, str): 入力のタイプ（'latlon', 'address'）と元のテキストのタプル。
    """
    if LATLON_PATTERN.match(text):
        return 'latlon', text
    
    return 'address', text
