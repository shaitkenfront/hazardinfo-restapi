import unittest
from unittest.mock import patch
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from lambda_function import lambda_handler, get_hazard_from_input, validate_coordinates


class TestLambdaFunction(unittest.TestCase):
    
    def test_validate_coordinates(self):
        """座標の妥当性検証のテスト"""
        # 有効な座標
        is_valid, message = validate_coordinates(35.6586, 139.7454)
        self.assertTrue(is_valid)
        self.assertIsNone(message)
        
        # 無効な緯度（範囲外）
        is_valid, message = validate_coordinates(50.0, 139.7454)
        self.assertFalse(is_valid)
        self.assertIn("緯度は24.0〜46.0", message)
        
        # 無効な経度（範囲外）
        is_valid, message = validate_coordinates(35.6586, 150.0)
        self.assertFalse(is_valid)
        self.assertIn("経度は123.0〜146.0", message)

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_datum_wgs84(self, mock_hazard_info, mock_convert):
        """datum=wgs84パラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}
        
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'datum': 'wgs84'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['datum'], 'wgs84')
        self.assertIn('入力座標系: wgs84', body['source'])
        mock_convert.assert_not_called()  # wgs84の場合は変換されない

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_datum_tokyo(self, mock_hazard_info, mock_convert):
        """datum=tokyoパラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}
        
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'datum': 'tokyo'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['datum'], 'tokyo')
        self.assertIn('入力座標系: tokyo', body['source'])
        mock_convert.assert_called_once()  # tokyoの場合は変換される

    def test_lambda_handler_with_invalid_datum(self):
        """無効なdatumパラメータのテスト"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'datum': 'invalid'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'Invalid datum parameter')

    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_default_datum(self, mock_hazard_info):
        """datumパラメータ省略時のデフォルト動作テスト"""
        mock_hazard_info.return_value = {"test": "data"}
        
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['datum'], 'wgs84')  # デフォルトはwgs84

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.input_parser.parse_input_type')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_get_hazard_from_input_with_datum(self, mock_hazard_info, mock_parse, mock_convert):
        """get_hazard_from_inputでのdatumパラメータテスト"""
        mock_parse.return_value = ('latlon', '35.6586,139.7454')
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}
        
        # WGS84の場合
        result = get_hazard_from_input('35.6586,139.7454', 'wgs84')
        self.assertEqual(result['status'], 'success')
        mock_convert.assert_not_called()  # wgs84の場合は変換されない
        
        # 日本測地系の場合
        mock_convert.reset_mock()
        result = get_hazard_from_input('35.6586,139.7454', 'tokyo')
        self.assertEqual(result['status'], 'success')
        mock_convert.assert_called()  # tokyoの場合は変換される

    def test_api_examples_include_datum(self):
        """APIのサンプル例にdatumパラメータが含まれていることを確認"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        
        # GET例にdatumが含まれていることを確認
        self.assertIn('datum=wgs84', body['examples']['coordinate_input']['GET'])
        self.assertIn('datum=wgs84', body['examples']['flexible_input']['GET'])
        
        # POST例にdatumが含まれていることを確認
        self.assertIn('"datum": "wgs84"', body['examples']['coordinate_input']['POST'])

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_hazard_types(self, mock_hazard_info, mock_convert):
        """hazard_typesパラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"jshis_prob_50": {"max_prob": 0.05, "center_prob": 0.03}}
        
        # GETリクエスト（カンマ区切り）
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'hazard_types': 'earthquake,flood'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['requested_hazard_types'], ['earthquake', 'flood'])
        mock_hazard_info.assert_called_with(35.6586, 139.7454, ['earthquake', 'flood'], False)

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_hazard_types_post(self, mock_hazard_info, mock_convert):
        """POSTリクエストでのhazard_typesパラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"tsunami_inundation": {"max_info": "浸水想定なし", "center_info": "浸水想定なし"}}
        
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'lat': 35.6586,
                'lon': 139.7454,
                'hazard_types': ['tsunami', 'landslide']
            })
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['requested_hazard_types'], ['tsunami', 'landslide'])
        mock_hazard_info.assert_called_with(35.6586, 139.7454, ['tsunami', 'landslide'], False)

    def test_lambda_handler_with_invalid_hazard_types(self):
        """無効なhazard_typesパラメータのテスト"""  
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'hazard_types': 'invalid_type,earthquake'
            }
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'Invalid hazard_types parameter')
        self.assertIn('invalid_type', body['message'])

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.input_parser.parse_input_type')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_get_hazard_from_input_with_hazard_types(self, mock_hazard_info, mock_parse, mock_convert):
        """get_hazard_from_inputでのhazard_typesパラメータテスト"""
        mock_parse.return_value = ('latlon', '35.6586,139.7454')
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}
        
        result = get_hazard_from_input('35.6586,139.7454', 'wgs84', ['earthquake', 'tsunami'])
        
        self.assertEqual(result['status'], 'success')
        mock_hazard_info.assert_called_with(35.6586, 139.7454, ['earthquake', 'tsunami'], False)

    def test_api_examples_include_hazard_types(self):
        """APIのサンプル例にhazard_typesパラメータが含まれていることを確認"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        
        # GET例にhazard_typesが含まれていることを確認
        self.assertIn('hazard_types=', body['examples']['coordinate_input']['GET'])
        self.assertIn('hazard_types=', body['examples']['flexible_input']['GET'])
        
        # POST例にhazard_typesが含まれていることを確認
        self.assertIn('"hazard_types":', body['examples']['coordinate_input']['POST'])
        
        # hazard_types_optionsが含まれていることを確認
        self.assertIn('hazard_types_options', body)
        self.assertIn('earthquake', body['hazard_types_options'])
        self.assertEqual(body['hazard_types_options']['earthquake'], '地震発生確率')
        
        # datum_optionsが存在することを確認
        self.assertIn('datum_options', body)
        self.assertIn('wgs84', body['datum_options'])
        self.assertIn('tokyo', body['datum_options'])


if __name__ == '__main__':
    unittest.main()