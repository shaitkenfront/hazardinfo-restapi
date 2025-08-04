import os
import requests

# 環境変数からAPIキーを取得
API_KEY = os.environ.get('GOOGLE_API_KEY')

# 都道府県コードの辞書
PREF_CODES = {
    '01': '北海道',
    '02': '青森県',
    '03': '岩手県',
    '04': '宮城県',
    '05': '秋田県',
    '06': '山形県',
    '07': '福島県',
    '08': '茨城県',
    '09': '栃木県',
    '10': '群馬県',
    '11': '埼玉県',
    '12': '千葉県',
    '13': '東京都',
    '14': '神奈川県',
    '15': '新潟県',
    '16': '富山県',
    '17': '石川県',
    '18': '福井県',
    '19': '山梨県',
    '20': '長野県',
    '21': '岐阜県',
    '22': '静岡県',
    '23': '愛知県',
    '24': '三重県',
    '25': '滋賀県',
    '26': '京都府',
    '27': '大阪府',
    '28': '兵庫県',
    '29': '奈良県',
    '30': '和歌山県',
    '31': '鳥取県',
    '32': '島根県',
    '33': '岡山県',
    '34': '広島県',
    '35': '山口県',
    '36': '徳島県',
    '37': '香川県',
    '38': '愛媛県',
    '39': '高知県',
    '40': '福岡県',
    '41': '佐賀県',
    '42': '長崎県',
    '43': '熊本県',
    '44': '大分県',
    '45': '宮崎県',
    '46': '鹿児島県',
    '47': '沖縄県'
}

GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def geocode(address: str) -> tuple[float, float] | None:
    """
    住所文字列を緯度・経度に変換し、日本測地系に変換する。

    Args:
        address: 日本語の住所文字列。

    Returns:
        tuple[float, float] | None: 日本測地系の (緯度, 経度) のタプル。変換失敗時はNone。
    """
    api_key = os.environ.get('GOOGLE_API_KEY')
    
    if not api_key:
        print("Google Geocoding API key is not configured.")
        return None

    params = {
        'address': address,
        'key': api_key,
        'language': 'ja'
    }
    
    try:
        response = requests.get(GEOCODING_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            wgs_lat, wgs_lon = location['lat'], location['lng']
            # 世界測地系から日本測地系へ変換
            tokyo_lat, tokyo_lon = convert_wgs84_to_tokyo_datum(wgs_lat, wgs_lon)
            return tokyo_lat, tokyo_lon
        else:
            print(f"Geocoding API Error: {data['status']}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling Geocoding API: {e}")
        return None

def convert_wgs84_to_tokyo_datum(lat: float, lon: float) -> tuple[float, float]:
    """
    世界測地系（WGS84）から日本測地系（Tokyo Datum）へ簡易変換する。

    Args:
        lat: 世界測地系の緯度。
        lon: 世界測地系の経度。

    Returns:
        tuple[float, float]: 日本測地系の (緯度, 経度) のタプル。
    """
    tokyo_lat = lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017
    tokyo_lon = lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040
    return tokyo_lat, tokyo_lon

def convert_tokyo_datum_to_wgs84(lat: float, lon: float) -> tuple[float, float]:
    """
    日本測地系（Tokyo Datum）から世界測地系（WGS84）へ簡易変換する。

    Args:
        lat: 日本測地系の緯度。
        lon: 日本測地系の経度。

    Returns:
        tuple[float, float]: 世界測地系の (緯度, 経度) のタプル。
    """
    wgs_lat = lat + 0.00010695 * lat - 0.000017464 * lon - 0.0046017
    wgs_lon = lon + 0.000046038 * lat + 0.000083043 * lon - 0.010040
    return wgs_lat, wgs_lon

def reverse_geocode(lat: float, lon: float) -> str | None:
    """
    緯度・経度を住所文字列に変換する（逆ジオコーディング）。

    Args:
        lat: 緯度。
        lon: 経度。

    Returns:
        str | None: 住所文字列。変換失敗時はNone。
    """
    api_key = os.environ.get('GOOGLE_API_KEY')
    
    if not api_key:
        print("Google Geocoding API key is not configured.")
        return None

    params = {
        'latlng': f'{lat},{lon}',
        'key': api_key,
        'language': 'ja'
    }

    try:
        response = requests.get(GEOCODING_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'OK':
            # 最も適切と思われる住所を返す
            return data['results'][0]['formatted_address']
        else:
            print(f"Reverse Geocoding API Error: {data['status']}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling Reverse Geocoding API: {e}")
        return None
    
def get_pref_code(lat: float, lon: float) -> str | None:
    """
    緯度・経度から都道府県コードを取得する。

    Args:
        lat: 緯度。
        lon: 経度。

    Returns:
        str | None: 都道府県コード。取得失敗時はNone。
    """
    address = reverse_geocode(lat, lon)
    if not address:
        return None

    # 都道府県名を抽出
    for pref_code, pref_name in PREF_CODES.items():
        if pref_name in address:
            return pref_code

    return None