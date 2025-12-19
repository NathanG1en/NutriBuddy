# backend/services/usda_client.py
"""USDA FoodData Central API client."""

import requests
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class USDAClient:
    """Handles all USDA API communication."""

    BASE_URL = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def search(self, query: str) -> list[dict]:
        """Search for foods by name."""
        response = self._session.post(
            f"{self.BASE_URL}/foods/search",
            params={"api_key": self._api_key},
            json={"query": query}
        )
        response.raise_for_status()
        return response.json().get("foods", [])

    def get_food(self, fdc_id: int) -> Optional[dict]:
        """Get detailed food data by FDC ID."""
        response = self._session.get(
            f"{self.BASE_URL}/food/{fdc_id}",
            params={"api_key": self._api_key}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()