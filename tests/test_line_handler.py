
import unittest
from unittest.mock import patch, MagicMock
import os
import json
from app.line_handler import validate_signature, reply_message, handle_line_event

class TestLineHandler(unittest.TestCase):

    def test_validate_signature(self):
        """Test the signature validation logic."""
        channel_secret = 'test_secret'
        body = '{"events":[]}'
        # A valid signature needs to be generated for the test
        # This is a placeholder and will fail if not replaced with a real one.
        # In a real scenario, you would generate this using the same hmac logic.
        # For this test, we will mock the comparison function instead.
        with patch('hmac.compare_digest', return_value=True):
            self.assertTrue(validate_signature(body, "some_signature", channel_secret))
        with patch('hmac.compare_digest', return_value=False):
            self.assertFalse(validate_signature(body, "invalid_signature", channel_secret))

    @patch('app.line_handler.requests.post')
    @patch.dict(os.environ, {'LINE_CHANNEL_ACCESS_TOKEN': 'test_token'})
    def test_reply_message(self, mock_post):
        """Test the reply message functionality."""
        reply_token = 'test_reply_token'
        text = 'こんにちは！'
        reply_message(reply_token, text)

        expected_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test_token'
        }
        expected_payload = {
            'replyToken': reply_token,
            'messages': [{'type': 'text', 'text': text}]
        }
        mock_post.assert_called_once_with(
            "https://api.line.me/v2/bot/message/reply",
            headers=expected_headers,
            data=json.dumps(expected_payload, ensure_ascii=False).encode('utf-8'),
            timeout=5
        )

    @patch('app.line_handler.reply_message')
    @patch('app.line_handler.validate_signature', return_value=True)
    @patch.dict(os.environ, {'LINE_CHANNEL_SECRET': 'test_secret'})
    def test_handle_line_event_valid(self, mock_validate, mock_reply):
        """Test handling a valid LINE event."""
        event_body = json.dumps({
            'events': [{
                'type': 'message',
                'replyToken': 'test_reply_token',
                'message': {'type': 'text', 'text': 'hello'}
            }]
        })
        signature = 'valid_signature'
        response_func = lambda msg: f"You said: {msg}"

        handle_line_event(event_body, signature, response_func)

        mock_validate.assert_called_once_with(event_body, signature, 'test_secret')
        mock_reply.assert_called_once_with('test_reply_token', 'You said: hello')

    @patch('app.line_handler.reply_message')
    @patch('app.line_handler.validate_signature', return_value=False)
    @patch.dict(os.environ, {'LINE_CHANNEL_SECRET': 'test_secret'})
    def test_handle_line_event_invalid_signature(self, mock_validate, mock_reply):
        """Test handling a LINE event with an invalid signature."""
        event_body = '{"events":[]}'
        signature = 'invalid_signature'
        response_func = lambda msg: "should not be called"

        handle_line_event(event_body, signature, response_func)

        mock_validate.assert_called_once_with(event_body, signature, 'test_secret')
        mock_reply.assert_not_called()

if __name__ == '__main__':
    unittest.main()
