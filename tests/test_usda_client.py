# tests/test_usda_client.py
"""Tests for USDAClient."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from backend.services.usda_client import USDAClient


@pytest.fixture
def client():
    return USDAClient(api_key="TEST_API_KEY", timeout=5.0, max_retries=2)


@pytest.mark.asyncio
async def test_search_async_success(client):
    mock_response = httpx.Response(
        200,
        json={"foods": [{"fdcId": 101, "description": "Apple, raw"}]},
        request=httpx.Request("POST", "https://api.nal.usda.gov/fdc/v1/foods/search"),
    )

    with patch.object(client, "_request_with_retry", AsyncMock(return_value=mock_response)):
        results = await client.search_async("apple")
        assert len(results) == 1
        assert results[0]["fdcId"] == 101
        assert results[0]["description"] == "Apple, raw"


@pytest.mark.asyncio
async def test_get_food_async_not_found(client):
    mock_response = httpx.Response(
        404,
        request=httpx.Request("GET", "https://api.nal.usda.gov/fdc/v1/food/999999"),
    )

    with patch.object(client, "_request_with_retry", AsyncMock(return_value=mock_response)):
        result = await client.get_food_async(999999)
        assert result is None


@pytest.mark.asyncio
async def test_get_foods_batch_async(client):
    async def mock_get_food(fid):
        if fid == 1:
            return {"fdcId": 1, "description": "Food 1"}
        elif fid == 2:
            return {"fdcId": 2, "description": "Food 2"}
        return None

    with patch.object(client, "get_food_async", side_effect=mock_get_food):
        batch = await client.get_foods_batch_async([1, 2, 3])
        assert batch[1]["description"] == "Food 1"
        assert batch[2]["description"] == "Food 2"
        assert batch[3] is None
