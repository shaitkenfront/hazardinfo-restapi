
import unittest
from app.input_parser import parse_input_type

class TestInputParser(unittest.TestCase):

    def test_parse_latlon(self):
        """Test that valid lat,lon strings are correctly identified."""
        test_cases = [
            "35.6895,139.6917",
            "-34.6037, -58.3816",
            "40.7128, -74.0060",
            "   35.6895  ,  139.6917   ", # with whitespace
            "0,0",
            "90,180",
            "-90,-180",
        ]
        for text in test_cases:
            with self.subTest(text=text):
                self.assertEqual(parse_input_type(text), ('latlon', text))

    def test_parse_address(self):
        """Test that addresses are correctly identified."""
        test_cases = [
            "東京都千代田区",
            "大阪府大阪市北区梅田",
            "Hokkaido, Japan",
            "123 Main St, Anytown, USA",
            "", # empty string
            "35.6895, 139.6917, extra", # extra comma
            "not a coordinate",
        ]
        for text in test_cases:
            with self.subTest(text=text):
                self.assertEqual(parse_input_type(text), ('address', text))

if __name__ == '__main__':
    unittest.main()
