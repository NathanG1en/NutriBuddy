# backend/services/usda_client.py
"""
USDA FoodData Central API client with async concurrency, connection pooling,
and exponential backoff retry handling.
"""

import asyncio
import logging
import random
from typing import Optional
import httpx
import requests

logger = logging.getLogger(__name__)


class USDAClient:
    """
    Handles all USDA API communication with both asynchronous and synchronous
    capabilities, connection pooling, and resilient retry policies.
    """

    BASE_URL = "https://api.nal.usda.gov/fdc/v1"

    def __init__(
        self,
        api_key: str,
        timeout: float = 12.0,
        max_connections: int = 40,
        max_keepalive_connections: int = 20,
        max_retries: int = 3,
        rate_limit_concurrency: int = 8,
    ):
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries

        # Semaphore to protect from exceeding API rate limits
        self._semaphore = asyncio.Semaphore(rate_limit_concurrency)

        # Async client configuration
        self._async_client_limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._async_client_timeout = httpx.Timeout(timeout, connect=5.0)
        self._async_client: Optional[httpx.AsyncClient] = None

        # Synchronous fallback session
        self._sync_session = requests.Session()
        self._sync_session.headers["Content-Type"] = "application/json"

    def _get_async_client(self) -> httpx.AsyncClient:
        """Lazily initialize the httpx AsyncClient within the active event loop."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                limits=self._async_client_limits,
                timeout=self._async_client_timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._async_client

    async def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Execute an HTTP request with exponential backoff and jitter for 429 and 5xx errors.
        """
        client = self._get_async_client()
        base_delay = 0.5

        for attempt in range(1, self._max_retries + 1):
            try:
                async with self._semaphore:
                    response = await client.request(method, url, **kwargs)

                # Return on success or standard client error (e.g. 404 Not Found)
                if response.status_code == 404 or response.status_code < 400:
                    return response

                # Rate limited (429) or transient server errors (5xx)
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    logger.warning(
                        f"USDA API returned {response.status_code} on attempt {attempt}/{self._max_retries}. Backing off."
                    )
                else:
                    response.raise_for_status()

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                logger.warning(
                    f"USDA API network/timeout on attempt {attempt}/{self._max_retries}: {err}"
                )
                if attempt == self._max_retries:
                    raise

            if attempt < self._max_retries:
                # Exponential backoff with random jitter: 2^(attempt-1) * base_delay + jitter
                delay = (2 ** (attempt - 1)) * base_delay + random.uniform(0.1, 0.4)
                await asyncio.sleep(delay)

        # Final attempt
        async with self._semaphore:
            response = await client.request(method, url, **kwargs)
            if response.status_code != 404:
                response.raise_for_status()
            return response

    async def search_async(self, query: str, page_size: int = 15) -> list[dict]:
        """
        Asynchronously search for foods by name.
        """
        url = f"{self.BASE_URL}/foods/search"
        params = {"api_key": self._api_key}
        payload = {"query": query, "pageSize": page_size}

        try:
            response = await self._request_with_retry(
                "POST", url, params=params, json=payload
            )
            if response.status_code == 200:
                return response.json().get("foods", [])
            return []
        except Exception as e:
            logger.error(f"Error in USDA search_async for '{query}': {e}")
            return []

    async def get_food_async(self, fdc_id: int) -> Optional[dict]:
        """
        Asynchronously get detailed food data by FDC ID.
        """
        url = f"{self.BASE_URL}/food/{fdc_id}"
        params = {"api_key": self._api_key}

        try:
            response = await self._request_with_retry("GET", url, params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error in USDA get_food_async for FDC ID {fdc_id}: {e}")
            return None

    async def get_foods_batch_async(self, fdc_ids: list[int]) -> dict[int, Optional[dict]]:
        """
        Fetch multiple foods concurrently using asyncio.gather.
        Returns a mapping of fdc_id -> food details dict.
        """
        if not fdc_ids:
            return {}

        unique_ids = list(set(fdc_ids))
        tasks = [self.get_food_async(fid) for fid in unique_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        food_map: dict[int, Optional[dict]] = {}
        for fid, res in zip(unique_ids, results):
            if isinstance(res, Exception):
                logger.error(f"Failed to fetch food details for {fid}: {res}")
                food_map[fid] = None
            else:
                food_map[fid] = res

        return food_map

    # --- Synchronous compatibility methods ---

    def search(self, query: str) -> list[dict]:
        """Synchronous search (backwards compatibility)."""
        try:
            response = self._sync_session.post(
                f"{self.BASE_URL}/foods/search",
                params={"api_key": self._api_key},
                json={"query": query},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json().get("foods", [])
        except Exception as e:
            logger.error(f"Error in synchronous USDA search for '{query}': {e}")
            return []

    def get_food(self, fdc_id: int) -> Optional[dict]:
        """Synchronous get_food (backwards compatibility)."""
        try:
            response = self._sync_session.get(
                f"{self.BASE_URL}/food/{fdc_id}",
                params={"api_key": self._api_key},
                timeout=self._timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error in synchronous USDA get_food for {fdc_id}: {e}")
            return None

    async def close(self):
        """Close the underlying HTTP clients."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
        self._sync_session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()