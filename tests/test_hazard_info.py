import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from io import BytesIO
from app import hazard_info

class TestHazardInfo(unittest.TestCase):

    def test_latlon_to_gsi_tile_pixel(self):
        """Test the coordinate conversion function."""
        zoom, x, y, px, py = hazard_info.latlon_to_gsi_tile_pixel(35.6895, 139.6917, 17)
        self.assertEqual(zoom, 17)
        self.assertEqual(x, 116396)
        self.assertEqual(y, 51609)
        self.assertEqual(px, 50)
        self.assertEqual(py, 145)

    def test_format_jshis_probability(self):
        """Test the J-SHIS probability formatting function."""
        self.assertEqual(hazard_info._format_jshis_probability(0.12345), "12%")
        self.assertEqual(hazard_info._format_jshis_probability("0.987"), "98%")
        self.assertEqual(hazard_info._format_jshis_probability(None), "データなし")
        self.assertEqual(hazard_info._format_jshis_probability("invalid"), "データ解析失敗")

    def test_format_hazard_output_string(self):
        """Test the generic hazard output formatting function."""
        self.assertEqual(hazard_info._format_hazard_output_string("10m", "5m"), " 周辺100mの最大: 10m\n 中心点: 5m")
        self.assertEqual(hazard_info._format_hazard_output_string("あり", "なし"), " 周辺100mの最大: あり\n 中心点: なし")
        self.assertEqual(hazard_info._format_hazard_output_string(None, None, "データなし"), "データなし")
        self.assertEqual(hazard_info._format_hazard_output_string("10m", None, "データなし"), " 周辺100mの最大: 10m\n 中心点: データなし")

    @patch('app.hazard_info.requests.get')
    def test_get_jshis_info(self, mock_get):
        """Test fetching J-SHIS earthquake probability."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'features': [{'properties': {'T30_I50_PS': '0.5', 'T30_I60_PS': '0.1'}}]
        }
        mock_get.return_value = mock_response

        result = hazard_info.get_jshis_info(35.0, 139.0)
        self.assertAlmostEqual(result['max_prob_50'], 0.5)
        self.assertAlmostEqual(result['center_prob_60'], 0.1)

    @patch('app.hazard_info.requests.get')
    def test_get_max_info_from_tile(self, mock_get):
        """Test the generic tile fetching and processing function."""
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        img.putpixel((10, 20), (255, 0, 0))
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        buffer.seek(0)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = buffer.read()
        mock_get.return_value = mock_response

        with patch('app.hazard_info.latlon_to_gsi_tile_pixel') as mock_latlon_to_tile:
            tile_and_pixel_for_center = (17, 1, 1, 10, 20)
            tile_and_pixel_for_edge = (17, 1, 1, 100, 100)
            
            side_effect_list = [tile_and_pixel_for_center] + [tile_and_pixel_for_edge] * 4
            side_effect_list += side_effect_list # Double it for the second loop
            
            mock_latlon_to_tile.side_effect = side_effect_list

            color_map = {(255, 0, 0): {"description": "High Risk", "weight": 10}}
            result = hazard_info._get_max_info_from_tile(
                35.0, 139.0, "dummy_url/{z}/{x}/{y}.png", 17, color_map, "No Risk"
            )

            self.assertEqual(result['center_info'], "High Risk")
            self.assertEqual(result['max_info'], "High Risk")

    @patch('app.hazard_info.requests.get')
    def test_get_flood_keizoku_info_from_gsi_tile(self, mock_get):
        """Test fetching flood keizoku info from GSI tile."""
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        # Test with a color from FLOOD_KEIZOKU_COLOR_MAP
        img.putpixel((10, 20), (255, 40, 0)) # 1週間～2週間未満
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        buffer.seek(0)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = buffer.read()
        mock_get.return_value = mock_response

        with patch('app.hazard_info.latlon_to_gsi_tile_pixel') as mock_latlon_to_tile:
            # Mock the return value of latlon_to_gsi_tile_pixel
            # The exact values don't matter as much as the consistency
            tile_and_pixel_for_center = (16, 1, 1, 10, 20)
            tile_and_pixel_for_edge = (16, 1, 1, 100, 100)
            
            # Create a side_effect list for the mock
            side_effect_list = [tile_and_pixel_for_center] + [tile_and_pixel_for_edge] * 8 # 1 center + 8 directions
            mock_latlon_to_tile.side_effect = side_effect_list

            result = hazard_info.get_flood_keizoku_info_from_gsi_tile(35.0, 139.0)

            self.assertEqual(result['center_info'], "1週間～2週間未満")
            self.assertEqual(result['max_info'], "1週間～2週間未満")

    @patch('app.hazard_info.geojsonhelper.load_large_geojson')
    @patch('app.hazard_info.geocoding.get_pref_code', return_value='13')
    def test_get_large_scale_filled_land_info(self, mock_get_pref, mock_load_geojson):
        """Test fetching large scale filled land info."""
        mock_geojson = {
            "type": "FeatureCollection",
            "features": [{
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[138.0, 34.0], [140.0, 34.0], [140.0, 36.0], [138.0, 36.0], [138.0, 34.0]]]
                },
                "properties": {}
            }]
        }
        mock_load_geojson.return_value = mock_geojson

        result = hazard_info.get_large_scale_filled_land_info_from_geojson(35.0, 139.0)
        self.assertEqual(result['center_info'], "あり")
        self.assertEqual(result['max_info'], "あり")

    @patch('app.hazard_info.get_jshis_info')
    @patch('app.hazard_info.get_inundation_depth_from_gsi_tile')
    @patch('app.hazard_info.get_tsunami_inundation_info_from_gsi_tile')
    @patch('app.hazard_info.get_flood_keizoku_info_from_gsi_tile')
    def test_get_selective_hazard_info_earthquake_only(self, mock_flood_keizoku, mock_tsunami, mock_flood, mock_jshis):
        """Test selective hazard info retrieval - earthquake only."""
        mock_jshis.return_value = {
            'max_prob_50': 0.05,
            'center_prob_50': 0.03,
            'max_prob_60': 0.02,
            'center_prob_60': 0.01
        }
        
        result = hazard_info.get_selective_hazard_info(35.0, 139.0, ['earthquake'])
        
        # Only earthquake data should be present
        self.assertIn('jshis_prob_50', result)
        self.assertIn('jshis_prob_60', result)
        self.assertNotIn('inundation_depth', result)
        self.assertNotIn('tsunami_inundation', result)
        self.assertNotIn('flood_keizoku', result)
        
        # J-SHIS should be called, others should not
        mock_jshis.assert_called_once_with(35.0, 139.0, False)
        mock_flood.assert_not_called()
        mock_tsunami.assert_not_called()
        mock_flood_keizoku.assert_not_called()

    @patch('app.hazard_info.get_jshis_info')
    @patch('app.hazard_info.get_inundation_depth_from_gsi_tile')
    @patch('app.hazard_info.get_tsunami_inundation_info_from_gsi_tile')
    @patch('app.hazard_info.get_high_tide_inundation_info_from_gsi_tile')
    @patch('app.hazard_info.get_large_scale_filled_land_info_from_geojson')
    @patch('app.hazard_info.get_debris_flow_info_from_gsi_tile')
    @patch('app.hazard_info.get_steep_slope_info_from_gsi_tile')
    @patch('app.hazard_info.get_landslide_info_from_gsi_tile')
    def test_get_selective_hazard_info_multiple_types(self, mock_landslide, mock_steep, mock_debris, 
                                                     mock_large_fill, mock_high_tide, mock_tsunami, 
                                                     mock_flood, mock_jshis):
        """Test selective hazard info retrieval - multiple types."""
        # Setup mocks
        mock_jshis.return_value = {'max_prob_50': 0.05, 'center_prob_50': 0.03, 'max_prob_60': 0.02, 'center_prob_60': 0.01}
        mock_flood.return_value = {'max_depth': '3m以上5m未満', 'center_depth': '0.5m未満'}
        mock_tsunami.return_value = {'max_info': '浸水想定なし', 'center_info': '浸水想定なし'}
        
        result = hazard_info.get_selective_hazard_info(35.0, 139.0, ['earthquake', 'flood', 'tsunami'])
        
        # Specified data should be present
        self.assertIn('jshis_prob_50', result)
        self.assertIn('inundation_depth', result)
        self.assertIn('tsunami_inundation', result)
        
        # Not specified data should not be present
        self.assertNotIn('hightide_inundation', result)
        self.assertNotIn('large_fill_land', result)
        self.assertNotIn('landslide_hazard', result)
        
        # Called functions should be called
        mock_jshis.assert_called_once_with(35.0, 139.0, False)
        mock_flood.assert_called_once_with(35.0, 139.0, False)
        mock_tsunami.assert_called_once_with(35.0, 139.0, False)
        
        # Not called functions should not be called
        mock_high_tide.assert_not_called()
        mock_large_fill.assert_not_called()
        mock_debris.assert_not_called()

    @patch('app.hazard_info.get_selective_hazard_info')
    def test_get_all_hazard_info_backward_compatibility(self, mock_selective):
        """Test that get_all_hazard_info calls get_selective_hazard_info with None."""
        mock_selective.return_value = {"test": "data"}
        
        result = hazard_info.get_all_hazard_info(35.0, 139.0)
        
        mock_selective.assert_called_once_with(35.0, 139.0, None, False)
        self.assertEqual(result, {"test": "data"})

    def test_get_selective_hazard_info_invalid_types(self):
        """Test selective hazard info with invalid hazard types."""
        # Invalid types should be ignored (no exception raised)
        result = hazard_info.get_selective_hazard_info(35.0, 139.0, ['invalid_type'])
        
        # Should return empty dict for invalid types
        self.assertEqual(result, {})

    def test_get_selective_hazard_info_empty_list(self):
        """Test selective hazard info with empty list."""
        result = hazard_info.get_selective_hazard_info(35.0, 139.0, [])
        
        # Should return empty dict for empty list
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()
