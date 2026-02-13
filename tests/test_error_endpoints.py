"""
Tests for error endpoints (error logging)
"""

import json
from unittest.mock import patch, MagicMock

from tests.test_base import BaseTestCase


class TestErrorEndpoints(BaseTestCase):
    """Test error-related endpoints"""

    @patch("logging.getLogger")
    def test_error_log_post_with_json_data(self, mock_get_logger):
        """Test POST /error/log with valid JSON data"""
        test_error_data = {
            "error": "JavaScript error occurred",
            "url": "/chat",
            "line": 42,
            "column": 15,
            "stack": "Error: Test error\n    at Function.test (/static/js/app.js:42:15)",
        }

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        response = self.client.post("/error/log", json=test_error_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    @patch("logging.getLogger")
    def test_error_log_post_without_json_data(self, mock_get_logger):
        """Test POST /error/log without JSON data"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        response = self.client.post("/error/log", content="not json")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    @patch("logging.getLogger")
    def test_error_log_post_empty_body(self, mock_get_logger):
        """Test POST /error/log with empty body"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        response = self.client.post("/error/log")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    @patch("logging.getLogger")
    def test_error_log_post_malformed_json(self, mock_get_logger):
        """Test POST /error/log with malformed JSON"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        response = self.client.post("/error/log", content="{'invalid': json}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    @patch("chat_client.endpoints.error_endpoints.log")
    def test_error_log_post_logs_error_data(self, mock_logger):
        """Test that error data is actually logged"""
        test_error_data = {"error": "Test error for logging", "source": "frontend"}

        response = self.client.post("/error/log", json=test_error_data)

        assert response.status_code == 200
        # Verify that the logger.error method was called with the error data
        mock_logger.error.assert_called_once_with(test_error_data)

    @patch("chat_client.endpoints.error_endpoints.log")
    def test_error_log_post_handles_exception_gracefully(self, mock_logger):
        """Test that POST /error/log handles exceptions gracefully"""
        # Make the logger raise an exception
        mock_logger.error.side_effect = Exception("Logging failed")

        response = self.client.post("/error/log", json={"test": "data"})

        # Even if logging fails, the endpoint should return success
        # to avoid breaking the frontend
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
