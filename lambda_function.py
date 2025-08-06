import json
from app import hazard_info, input_parser, geocoding
from app.hazard_info import ENABLE_LARGE_FILL_LAND


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


def get_hazard_from_input(input_text, datum='wgs84', hazard_types=None, precision='low'):
    """
    住所、緯度経度のいずれかの入力からハザード情報を取得する
    
    Args:
        input_text: 住所または緯度経度の文字列
        datum: 座標系 ('wgs84' または 'tokyo')。デフォルトは 'wgs84'
        hazard_types: 取得するハザード情報のリスト。Noneの場合は全て取得
        precision: 検索精度 ('low': 高速, 'high': 高精度)。デフォルトは'low'
    """
    input_type, value = input_parser.parse_input_type(input_text)
    lat, lon = None, None
    source_info = ""
    
    if input_type == 'latlon':
        try:
            lat, lon = map(float, value.split(','))
            # 座標系に応じて変換処理
            if datum == 'tokyo':
                # 日本測地系から世界測地系へ変換
                lat, lon = geocoding.convert_tokyo_datum_to_wgs84(lat, lon)
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
    
    # 精度をbool型に変換
    high_precision = precision == 'high'
    
    # ハザード情報を取得
    hazard_data = hazard_info.get_selective_hazard_info(lat, lon, hazard_types, high_precision)
    
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
        precision = None
        
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
            precision = query_params.get('precision', 'low')
        
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
                    precision = body_data.get('precision', 'low')
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
        valid_hazard_types = ['earthquake', 'flood', 'flood_keizoku', 'kaokutoukai_hanran', 'tsunami', 'high_tide', 'landslide', 'large_fill_land']
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

        # precisionの検証
        if precision not in ['low', 'high']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Invalid precision parameter',
                    'message': 'precision parameter must be either "low" (fast) or "high" (high accuracy)',
                    'received': precision
                })
            }

        # 入力方法を判定
        if input_text:
            # 住所・URL・座標文字列による入力
            print(f"Processing input text: {input_text}, datum: {datum}, hazard_types: {hazard_types}, precision: {precision}")
            result = get_hazard_from_input(input_text, datum, hazard_types, precision)
            
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
            if datum == 'tokyo':
                # 日本測地系から世界測地系へ変換
                lat_float, lon_float = geocoding.convert_tokyo_datum_to_wgs84(lat_float, lon_float)
            
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
            
            # 精度をbool型に変換
            high_precision = precision == 'high'
            
            print(f"Fetching hazard info for coordinates: {lat_float}, {lon_float} (input datum: {datum}, hazard_types: {hazard_types}, precision: {precision})")
            
            # ハザード情報の取得
            hazard_data = hazard_info.get_selective_hazard_info(lat_float, lon_float, hazard_types, high_precision)
            
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
            error_response = {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Missing parameters',
                    'message': 'Either input parameter or both lat and lon parameters are required',
                    'examples': {
                        'coordinate_input': {
                            'GET': '?lat=35.6586&lon=139.7454&datum=wgs84&hazard_types=earthquake,flood&precision=low',
                            'POST': '{"lat": 35.6586, "lon": 139.7454, "datum": "wgs84", "hazard_types": ["earthquake", "flood"], "precision": "low"}'
                        },
                        'flexible_input': {
                            'GET': '?input=東京都新宿区&datum=wgs84&hazard_types=tsunami,landslide&precision=high',
                            'POST': '{"input": "東京都新宿区", "datum": "wgs84", "hazard_types": ["tsunami", "landslide"], "precision": "high"}'
                        }
                    },
                    'datum_options': {
                        'wgs84': 'World Geodetic System 1984 (default)',
                        'tokyo': 'Tokyo Datum (Japanese Geodetic System)'
                    },
                    'hazard_types_options': {
                        'earthquake': '地震発生確率',
                        'flood': '想定最大浸水深',
                        'flood_keizoku': '浸水継続時間',
                        'kaokutoukai_hanran': '家屋倒壊等氾濫想定区域（氾濫流）',
                        'tsunami': '津波浸水想定',
                        'high_tide': '高潮浸水想定',
                        'landslide': '土砂災害警戒区域'
                    },
                    'precision_options': {
                        'low': 'Fast mode (default) - ~7 seconds response time',
                        'high': 'High accuracy mode - ~11-14 seconds response time'
                    }
                })
            }
            if ENABLE_LARGE_FILL_LAND:
                body_data = json.loads(error_response['body'])
                body_data['examples']['flexible_input']['GET'] += ',large_fill_land'
                body_data['examples']['flexible_input']['POST'] = '{"input": "東京都新宿区", "datum": "wgs84", "hazard_types": ["tsunami", "landslide", "large_fill_land"], "precision": "high"}'
                body_data['hazard_types_options']['large_fill_land'] = '大規模盛土造成地'
                error_response['body'] = json.dumps(body_data)
            return error_response
        
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