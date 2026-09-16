import sys
import os
import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

# Add Backend folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.openrouter_client import OpenRouterClient, parse_json_response
from app.config import settings

class TestOpenRouterClientRateLimit(unittest.TestCase):

    def setUp(self):
        self.client = OpenRouterClient()
        self.client.reset_metrics()

    def test_parse_json_response_clean(self):
        raw_text = '```json\n{"matched_code": "SGL", "wall_type": "INT"}\n```'
        parsed = parse_json_response(raw_text)
        self.assertEqual(parsed.get("matched_code"), "SGL")
        self.assertEqual(parsed.get("wall_type"), "INT")

    def test_retry_after_header_parsing(self):
        # 1. Integer/Float seconds header
        resp_numeric = MagicMock()
        resp_numeric.headers = {"retry-after": "5.5"}
        self.assertEqual(self.client._parse_retry_after(resp_numeric), 5.5)

        # 2. HTTP Date header
        resp_date = MagicMock()
        resp_date.headers = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        parsed_dt = self.client._parse_retry_after(resp_date)
        self.assertIsNotNone(parsed_dt)
        self.assertGreater(parsed_dt, 0.0)

        # 3. Missing header
        resp_none = MagicMock()
        resp_none.headers = {}
        self.assertIsNone(self.client._parse_retry_after(resp_none))

    def test_exponential_backoff_delay_calculation(self):
        # Attempt 1 (base 1.0s, jitter ±20%)
        d1 = self.client._calculate_backoff_delay(attempt=1)
        self.assertTrue(0.8 <= d1 <= 1.2, f"Attempt 1 delay {d1} outside expected [0.8, 1.2]")

        # Attempt 2 (base 2.0s)
        d2 = self.client._calculate_backoff_delay(attempt=2)
        self.assertTrue(1.6 <= d2 <= 2.4, f"Attempt 2 delay {d2} outside expected [1.6, 2.4]")

        # Respect explicit Retry-After header
        d_retry_after = self.client._calculate_backoff_delay(attempt=1, retry_after_seconds=10.0)
        self.assertTrue(8.0 <= d_retry_after <= 12.0, f"Retry-after delay {d_retry_after} outside expected [8.0, 12.0]")

    def test_mock_429_rate_limit_retry_and_success(self):
        """Simulates 2 HTTP 429 rate limit responses followed by 1 HTTP 200 success."""
        loop = asyncio.get_event_loop()

        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        resp_429 = httpx.Response(429, headers={"Retry-After": "0.1"}, json={"error": "rate limit"}, request=req)
        resp_200 = httpx.Response(200, json={"choices": [{"message": {"content": '{"status": "ok"}'}}]}, request=req)

        mock_post = AsyncMock(side_effect=[resp_429, resp_429, resp_200])

        with patch("httpx.AsyncClient.post", mock_post), \
             patch("asyncio.sleep", AsyncMock()):
            result = loop.run_until_complete(
                self.client.generate_chat(prompt="Test prompt", json_mode=True)
            )

        self.assertEqual(result, '{"status": "ok"}')
        metrics = self.client.get_metrics_summary()
        self.assertEqual(metrics["total_requests"], 1)
        self.assertEqual(metrics["total_successful_requests"], 1)
        self.assertEqual(metrics["total_429_hits"], 2)
        self.assertEqual(metrics["total_retries"], 2)
        self.assertEqual(metrics["total_exhausted_failures"], 0)

    def test_mock_429_exhaustion_max_retries(self):
        """Simulates 5 consecutive HTTP 429 responses causing clean retries exhaustion."""
        loop = asyncio.get_event_loop()

        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        resp_429 = httpx.Response(429, headers={"Retry-After": "0.1"}, json={"error": "rate limit"}, request=req)

        mock_post = AsyncMock(return_value=resp_429)

        with patch("httpx.AsyncClient.post", mock_post), \
             patch("asyncio.sleep", AsyncMock()):
            with self.assertRaises(httpx.HTTPStatusError):
                loop.run_until_complete(
                    self.client.generate_chat(prompt="Test prompt", json_mode=True)
                )

        metrics = self.client.get_metrics_summary()
        self.assertEqual(metrics["total_429_hits"], 5)
        self.assertEqual(metrics["total_retries"], 4)
        self.assertEqual(metrics["total_exhausted_failures"], 1)

    def test_mock_non_retryable_401_client_error(self):
        """Simulates HTTP 401 Unauthorized which MUST fail fast without retries."""
        loop = asyncio.get_event_loop()

        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        resp_401 = httpx.Response(401, json={"error": "unauthorized"}, request=req)

        mock_post = AsyncMock(return_value=resp_401)

        with patch("httpx.AsyncClient.post", mock_post):
            with self.assertRaises(httpx.HTTPStatusError):
                loop.run_until_complete(
                    self.client.generate_chat(prompt="Test prompt", json_mode=True)
                )

        metrics = self.client.get_metrics_summary()
        self.assertEqual(metrics["total_429_hits"], 0)
        self.assertEqual(metrics["total_retries"], 0)
        self.assertEqual(metrics["total_exhausted_failures"], 1)

    def test_bounded_concurrency_semaphore_limit(self):
        """
        Simulates 10 concurrent requests to generate_chat.
        Verifies that peak_in_flight NEVER exceeds OPENROUTER_CONCURRENCY_LIMIT (3).
        """
        loop = asyncio.get_event_loop()

        async def mock_slow_post(*args, **kwargs):
            await asyncio.sleep(0.05) # Simulate network latency
            req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"status": "ok"}'}}]}, request=req)

        with patch("httpx.AsyncClient.post", AsyncMock(side_effect=mock_slow_post)):
            tasks = [self.client.generate_chat(prompt=f"Task {i}") for i in range(10)]
            results = loop.run_until_complete(asyncio.gather(*tasks))

        self.assertEqual(len(results), 10)
        metrics = self.client.get_metrics_summary()
        self.assertEqual(metrics["total_requests"], 10)
        self.assertEqual(metrics["total_successful_requests"], 10)
        self.assertLessEqual(metrics["peak_in_flight"], settings.OPENROUTER_CONCURRENCY_LIMIT)

if __name__ == "__main__":
    unittest.main()
