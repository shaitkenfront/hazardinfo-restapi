import json
import boto3
from app import hazard_info, input_parser, geocoding


def validate_coordinates(lat, lon):
    """
    緯度経度の妥当性を検証する
    """
    try:
        lat_float = float(lat)
        lon_float = float(lon)
        
        # 日本の緯度経度の範囲をチェック
        if not (24.0 <= lat_float <= 46.0):
            return False, "緯度は24.0〜46.0の範囲で入力してください"
        
        if not (123.0 <= lon_float <= 146.0):
            return False, "経度は123.0〜146.0の範囲で入力してください"
            
        return True, None
    except ValueError:
        return False, "緯度・経度は数値で入力してください"


def get_hazard_from_input(input_text, datum='wgs84', hazard_types=None, search_points=4):
    """
    住所、緯度経度のいずれかの入力からハザード情報を取得する
    
    Args:
        input_text: 住所または緯度経度の文字列
        datum: 座標系 ('wgs84' または 'tokyo')。デフォルトは 'wgs84'
        hazard_types: 取得するハザード情報のリスト。Noneの場合は全て取得
        search_points: 検索点数 (4: 高速, 8: 高精度)。デフォルトは4
    """
    input_type, value = input_parser.parse_input_type(input_text)
    lat, lon = None, None
    property_address = None
    source_info = ""
    
    if input_type == 'latlon':
        try:
            lat, lon = map(float, value.split(','))
            # 座標系に応じて変換処理
            if datum == 'wgs84':
                # WGS84から日本測地系へ変換
                lat, lon = geocoding.convert_wgs84_to_tokyo_datum(lat, lon)
            source_info = f"座標: {lat}, {lon} (入力座標系: {datum})"
        except ValueError:
            return {
                'error': 'Invalid coordinate format',
                'message': '緯度・経度の形式が正しくありません。例: 35.6586, 139.7454'
            }
    
    elif input_type == 'address':
        try:
            lat, lon = geocoding.geocode(value)
            source_info = f"住所: {value}"
        except Exception as e:
            return {
                'error': 'Geocoding error',
                'message': f'住所の変換中にエラーが発生しました: {str(e)}'
            }
    
    if lat is None or lon is None:
        return {
            'error': 'Location not found',
            'message': '場所を特定できませんでした。住所やURLを確認してください。'
        }
    
    # 日本の範囲チェック
    is_valid, error_message = validate_coordinates(lat, lon)
    if not is_valid:
        return {
            'error': 'Invalid coordinates',
            'message': error_message
        }
    
    # ハザード情報を取得
    hazard_data = hazard_info.get_selective_hazard_info(lat, lon, hazard_types, search_points)
    
    return {
        'coordinates': {
            'latitude': lat,
            'longitude': lon
        },
        'source': source_info,
        'input_type': input_type,
        'hazard_info': hazard_data,
        'status': 'success'
    }


def lambda_handler(event, context):
    """
    REST APIで緯度経度を受け取ってハザード情報を返すLambda関数
    """
    try:
        # CORSヘッダーの設定
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        }
        
        # OPTIONSリクエスト（プリフライトリクエスト）への対応
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight response'})
            }
        
        # HTTPメソッドのチェック
        if event.get('httpMethod') not in ['GET', 'POST']:
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Method not allowed',
                    'message': 'Only GET and POST methods are supported'
                })
            }
        
        # パラメータの取得
        lat = None
        lon = None
        input_text = None
        datum = None
        hazard_types = None
        search_points = None
        
        if event.get('httpMethod') == 'GET':
            # GETリクエストの場合、クエリパラメータから取得
            query_params = event.get('queryStringParameters') or {}
            lat = query_params.get('lat')
            lon = query_params.get('lon')
            input_text = query_params.get('input')  # 住所やURLを受け取る新しいパラメータ
            datum = query_params.get('datum', 'wgs84')  # デフォルトはwgs84
            hazard_types_str = query_params.get('hazard_types')
            if hazard_types_str:
                hazard_types = [h.strip() for h in hazard_types_str.split(',')]
            search_points = int(query_params.get('search_points', 4))
        
        elif event.get('httpMethod') == 'POST':
            # POSTリクエストの場合、リクエストボディから取得
            body = event.get('body', '{}')
            if body:
                try:
                    body_data = json.loads(body)
                    lat = body_data.get('lat')
                    lon = body_data.get('lon')
                    input_text = body_data.get('input')  # 住所やURLを受け取る新しいパラメータ
                    datum = body_data.get('datum', 'wgs84')  # デフォルトはwgs84
                    hazard_types = body_data.get('hazard_types')
                    search_points = int(body_data.get('search_points', 4))
                except json.JSONDecodeError:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({
                            'error': 'Invalid JSON',
                            'message': 'Request body must be valid JSON'
                        })
                    }
        
        # datumパラメータの検証
        if datum not in ['wgs84', 'tokyo']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Invalid datum parameter',
                    'message': 'datum parameter must be either "wgs84" or "tokyo"',
                    'received': datum
                })
            }
        
        # hazard_typesの検証
        valid_hazard_types = ['earthquake', 'flood', 'tsunami', 'high_tide', 'large_fill_land', 'landslide']
        if hazard_types:
            invalid_types = [ht for ht in hazard_types if ht not in valid_hazard_types]
            if invalid_types:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'Invalid hazard_types parameter',
                        'message': f'Invalid hazard types: {invalid_types}',
                        'valid_types': valid_hazard_types
                    })
                }

        # search_pointsの検証
        if search_points not in [4, 8]:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Invalid search_points parameter',
                    'message': 'search_points parameter must be either 4 (fast) or 8 (high accuracy)',
                    'received': search_points
                })
            }

        # 入力方法を判定
        if input_text:
            # 住所・URL・座標文字列による入力
            print(f"Processing input text: {input_text}, datum: {datum}, hazard_types: {hazard_types}, search_points: {search_points}")
            result = get_hazard_from_input(input_text, datum, hazard_types, search_points)
            
            # エラーの場合
            if 'error' in result:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps(result)
                }
            
            # 成功の場合
            response_data = result
            response_data['requested_hazard_types'] = hazard_types
            
        elif lat is not None and lon is not None:
            # 従来の緯度経度による直接入力
            lat_float = float(lat)
            lon_float = float(lon)
            
            # 座標系に応じて変換処理
            if datum == 'wgs84':
                # WGS84から日本測地系へ変換
                lat_float, lon_float = geocoding.convert_wgs84_to_tokyo_datum(lat_float, lon_float)
            
            # 緯度経度の妥当性検証（変換後の座標で）
            is_valid, error_message = validate_coordinates(lat_float, lon_float)
            if not is_valid:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'Invalid coordinates',
                        'message': error_message
                    })
                }
            
            print(f"Fetching hazard info for coordinates: {lat_float}, {lon_float} (input datum: {datum}, hazard_types: {hazard_types}, search_points: {search_points})")
            
            # ハザード情報の取得
            hazard_data = hazard_info.get_selective_hazard_info(lat_float, lon_float, hazard_types, search_points)
            
            # レスポンスの構築
            response_data = {
                'coordinates': {
                    'latitude': lat_float,
                    'longitude': lon_float
                },
                'source': f"座標: {lat_float}, {lon_float} (入力座標系: {datum})",
                'input_type': 'latlon',
                'datum': datum,
                'requested_hazard_types': hazard_types,
                'hazard_info': hazard_data,
                'status': 'success'
            }
        
        else:
            # パラメータが不足している場合
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Missing parameters',
                    'message': 'Either input parameter or both lat and lon parameters are required',
                    'examples': {
                        'coordinate_input': {
                            'GET': '?lat=35.6586&lon=139.7454&datum=wgs84&hazard_types=earthquake,flood&search_points=4',
                            'POST': '{"lat": 35.6586, "lon": 139.7454, "datum": "wgs84", "hazard_types": ["earthquake", "flood"], "search_points": 4}'
                        },
                        'flexible_input': {
                            'GET': '?input=東京都新宿区&datum=wgs84&hazard_types=tsunami,landslide&search_points=8',
                            'POST': '{"input": "東京都新宿区", "datum": "wgs84", "hazard_types": ["tsunami", "landslide"], "search_points": 8}'
                        }
                    },
                    'datum_options': {
                        'wgs84': 'World Geodetic System 1984 (default)',
                        'tokyo': 'Tokyo Datum (Japanese Geodetic System)'
                    },
                    'hazard_types_options': {
                        'earthquake': '地震発生確率',
                        'flood': '想定最大浸水深',
                        'tsunami': '津波浸水想定',
                        'high_tide': '高潮浸水想定',
                        'large_fill_land': '大規模盛土造成地',
                        'landslide': '土砂災害警戒区域'
                    },
                    'search_points_options': {
                        '4': 'Fast mode (default) - ~7 seconds response time',
                        '8': 'High accuracy mode - ~11-14 seconds response time'
                    }
                })
            }
        
        print(response_data)
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': f'An error occurred while processing the request: {str(e)}'
            })
        }