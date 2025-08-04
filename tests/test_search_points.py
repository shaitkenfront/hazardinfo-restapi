import unittest
import json
from unittest.mock import patch
import lambda_function


class TestPrecisionParameter(unittest.TestCase):
    """precisionパラメータのテスト"""

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_precision_low(self, mock_hazard_info, mock_convert):
        """precision='low'のテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'precision': 'low'
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, False)

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_precision_high(self, mock_hazard_info, mock_convert):
        """precision='high'のテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'precision': 'high'
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, True)

    def test_lambda_handler_with_invalid_precision(self):
        """無効なprecisionパラメータのテスト"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'precision': 'medium'  # 無効な値
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'Invalid precision parameter')
        self.assertIn('precision parameter must be either "low" (fast) or "high" (high accuracy)', body['message'])

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_default_precision(self, mock_hazard_info, mock_convert):
        """precisionパラメータなし（デフォルト'low'）のテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454'
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, False)

    @patch('lambda_function.geocoding.convert_tokyo_datum_to_wgs84')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_post_with_precision(self, mock_hazard_info, mock_convert):
        """POSTリクエストでprecisionパラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'lat': 35.6586,
                'lon': 139.7454,
                'precision': 'high'
            })
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, True)


if __name__ == '__main__':
    unittest.main()