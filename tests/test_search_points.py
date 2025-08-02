import unittest
import json
from unittest.mock import patch, MagicMock
import lambda_function


class TestSearchPointsParameter(unittest.TestCase):
    """search_pointsパラメータのテスト"""

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_search_points_4(self, mock_hazard_info, mock_convert):
        """search_points=4のテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'search_points': '4'
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, 4)

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_with_search_points_8(self, mock_hazard_info, mock_convert):
        """search_points=8のテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'search_points': '8'
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, 8)

    def test_lambda_handler_with_invalid_search_points(self):
        """無効なsearch_pointsパラメータのテスト"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'lat': '35.6586',
                'lon': '139.7454',
                'search_points': '9'  # 無効な値
            }
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'Invalid search_points parameter')
        self.assertIn('search_points parameter must be either 4 (fast) or 8 (high accuracy)', body['message'])

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_default_search_points(self, mock_hazard_info, mock_convert):
        """search_pointsパラメータなし（デフォルト4）のテスト"""
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
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, 4)

    @patch('lambda_function.geocoding.convert_wgs84_to_tokyo_datum')
    @patch('lambda_function.hazard_info.get_selective_hazard_info')
    def test_lambda_handler_post_with_search_points(self, mock_hazard_info, mock_convert):
        """POSTリクエストでsearch_pointsパラメータのテスト"""
        mock_convert.return_value = (35.6586, 139.7454)
        mock_hazard_info.return_value = {"test": "data"}

        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'lat': 35.6586,
                'lon': 139.7454,
                'search_points': 8
            })
        }

        response = lambda_function.lambda_handler(event, {})

        self.assertEqual(response['statusCode'], 200)
        mock_hazard_info.assert_called_with(35.6586, 139.7454, None, 8)


if __name__ == '__main__':
    unittest.main()