import unittest
from unittest.mock import patch, MagicMock
import os
import requests  # Import requests for the exception test
from app.geocoding import geocode

class TestGeocoding(unittest.TestCase):

    @patch('app.geocoding.requests.get')
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_api_key'})
    def test_geocode_success(self, mock_get):
        """
        Test successful geocoding.
        """
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'OK',
            'results': [{
                'geometry': {
                    'location': {
                        'lat': 35.6895,
                        'lng': 139.6917
                    }
                }
            }]
        }
        mock_get.return_value = mock_response

        address = "東京都新宿区"
        result = geocode(address)
        self.assertEqual(result, (35.6927242838238, 139.6884965089559))

    @patch('app.geocoding.requests.get')
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_api_key'})
    def test_geocode_api_error(self, mock_get):
        """
        Test geocoding when the API returns an error status.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ZERO_RESULTS',
            'results': []
        }
        mock_get.return_value = mock_response

        address = "存在しない住所"
        result = geocode(address)
        self.assertIsNone(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_geocode_no_api_key(self):
        """
        Test geocoding when the API key is not set.
        """
        address = "東京都渋谷区"
        result = geocode(address)
        self.assertIsNone(result)

    @patch('app.geocoding.requests.get')
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_api_key'})
    def test_geocode_request_exception(self, mock_get):
        """
        Test geocoding when a request exception occurs.
        """
        mock_get.side_effect = requests.exceptions.RequestException("Test error")

        address = "東京都港区"
        result = geocode(address)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()