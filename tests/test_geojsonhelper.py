
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
from app.geojsonhelper import get_geojson_from_s3, load_large_geojson

class TestGeojsonHelper(unittest.TestCase):

    @patch('app.geojsonhelper.boto3.client')
    def test_get_geojson_from_s3(self, mock_boto_client):
        """Test getting GeoJSON from S3."""
        # Mock S3 client and its get_object method
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        geojson_data = {"type": "FeatureCollection", "features": []}
        geojson_body = json.dumps(geojson_data).encode('utf-8')

        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=geojson_body))
        }

        bucket = 'test-bucket'
        key = 'test.geojson'
        result = get_geojson_from_s3(bucket, key)

        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)
        self.assertEqual(result, geojson_data)

    @patch('app.geojsonhelper.boto3.client')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists', return_value=False) # Assume file doesn't exist
    def test_load_large_geojson_download(self, mock_exists, mock_file, mock_boto_client):
        """Test loading a large GeoJSON file that needs to be downloaded."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        bucket = 'test-bucket'
        key = 'large.geojson'
        local_path = f'/tmp/{os.path.basename(key)}'
        geojson_data = {"type": "Feature", "properties": {}, "geometry": None}

        # This part is tricky. We need to mock the file writing and then reading.
        # When open is called for writing, it does its thing.
        # When it's called for reading, we need it to return the geojson data.
        mock_file.side_effect = [
            mock_open().return_value, # for writing
            mock_open(read_data=json.dumps(geojson_data)).return_value # for reading
        ]

        result = load_large_geojson(bucket, key)

        mock_exists.assert_called_once_with(local_path)
        mock_s3.download_fileobj.assert_called_once()
        # Check that the file was opened for writing and then reading
        self.assertEqual(mock_file.call_count, 2)
        self.assertEqual(result, geojson_data)

    @patch('app.geojsonhelper.boto3.client')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({"cached": True}))
    @patch('os.path.exists', return_value=True) # Assume file exists
    def test_load_large_geojson_cached(self, mock_exists, mock_file, mock_boto_client):
        """Test loading a large GeoJSON file that is already cached."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        bucket = 'test-bucket'
        key = 'large.geojson'
        local_path = f'/tmp/{os.path.basename(key)}'

        result = load_large_geojson(bucket, key)

        mock_exists.assert_called_once_with(local_path)
        # S3 download should NOT be called
        mock_s3.download_fileobj.assert_not_called()
        # File should be opened for reading
        mock_file.assert_called_once_with(local_path, "r", encoding="utf-8")
        self.assertEqual(result, {"cached": True})

if __name__ == '__main__':
    unittest.main()
