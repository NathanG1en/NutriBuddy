import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from fastapi.testclient import TestClient

from backend.agent.graph import NutritionAgent
from backend.agent.tools import (
    calculate_recipe_nutrition,
    generate_label_image,
    search_recipe_knowledge,
)
from backend.api.main import app
from backend.dependencies import get_agent
from backend.api.security import get_current_user


def test_agent_extract_result_with_artifacts():
    agent = NutritionAgent.__new__(NutritionAgent)
    
    # Mock messages containing ToolMessages with artifacts and final AIMessage
    tool_label_msg = ToolMessage(
        content="Label generated",
        tool_call_id="call_1",
        artifact={
            "type": "label_image",
            "filename": "apple_pie_2026.png",
            "image_path": "/labels/apple_pie_2026.png",
            "food_name": "apple pie",
        },
    )
    tool_recipe_msg = ToolMessage(
        content="Nutrition calculated",
        tool_call_id="call_2",
        artifact={
            "type": "recipe_nutrition",
            "totals": {"calories": 450, "protein_g": 12},
            "ingredients": [{"name": "oats", "calories": 300}],
        },
    )
    ai_msg = AIMessage(content="Here is your nutrition label and recipe analysis!")

    raw_result = {"messages": [tool_label_msg, tool_recipe_msg, ai_msg]}
    extracted = agent._extract_result(raw_result)

    assert extracted["message"] == "Here is your nutrition label and recipe analysis!"
    assert extracted["image_path"] == "/labels/apple_pie_2026.png"
    assert extracted["exportable"]["type"] == "recipe_nutrition"
    assert len(extracted["artifacts"]) == 2


def test_agent_extract_result_fallback_regex():
    agent = NutritionAgent.__new__(NutritionAgent)
    ai_msg = AIMessage(content="I generated your label: /labels/banana_bread_123.png enjoy!")
    raw_result = {"messages": [ai_msg]}
    extracted = agent._extract_result(raw_result)

    assert extracted["image_path"] == "/labels/banana_bread_123.png"
    assert extracted["artifacts"] == []
    assert extracted["exportable"] is None


def test_search_recipe_knowledge_tool():
    mock_rag = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "To make vegan pancakes, combine 1 cup flour with almond milk."
    mock_doc.metadata = {"source": "Cookbook.pdf", "page": 14}
    mock_rag.query.return_value = [mock_doc]

    with patch("backend.dependencies.get_rag_service", return_value=mock_rag):
        res = search_recipe_knowledge.invoke({"query": "vegan pancake"})
        data = json.loads(res)
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["source"] == "Cookbook.pdf"
        assert data["results"][0]["page"] == 14
        assert "vegan pancakes" in data["results"][0]["content"]


def test_search_recipe_knowledge_empty():
    mock_rag = MagicMock()
    mock_rag.query.return_value = []

    with patch("backend.dependencies.get_rag_service", return_value=mock_rag):
        res = search_recipe_knowledge.invoke({"query": "obscure ingredient"})
        data = json.loads(res)
        assert "No matching knowledge base documents found" in data["message"]


def test_calculate_recipe_nutrition_tool_artifact():
    mock_service = MagicMock()
    mock_service.calculate_recipe.return_value = {
        "recipe_totals": {"calories": 300, "protein_g": 10},
        "ingredients": [{"name": "oats", "calories": 300, "grams": 80.0}],
    }

    with patch("backend.agent.tools._get_nutrition_service", return_value=mock_service):
        tool_call = {
            "name": "calculate_recipe_nutrition",
            "args": {"ingredients_input": "1 cup oats"},
            "id": "call_calc_1",
            "type": "tool_call",
        }
        tool_msg = calculate_recipe_nutrition.invoke(tool_call)

        parsed_content = json.loads(tool_msg.content)
        assert parsed_content["recipe_totals"]["calories"] == 300
        assert tool_msg.artifact["type"] == "recipe_nutrition"
        assert tool_msg.artifact["totals"]["calories"] == 300


def test_generate_label_image_tool_artifact(tmp_path):
    mock_label_svc = MagicMock()
    mock_label_svc.generate_image.return_value = b"fake-png-bytes"

    with patch("backend.agent.tools._get_label_service", return_value=mock_label_svc):
        nutrition_input = json.dumps({"calories": 200, "protein_g": 5})
        tool_call = {
            "name": "generate_label_image",
            "args": {
                "nutrition_json": nutrition_input,
                "food_name": "Greek Yogurt",
            },
            "id": "call_img_1",
            "type": "tool_call",
        }
        tool_msg = generate_label_image.invoke(tool_call)

        assert "✅ Nutrition label saved" in tool_msg.content
        assert tool_msg.artifact["type"] == "label_image"
        assert tool_msg.artifact["food_name"] == "Greek Yogurt"
        assert tool_msg.artifact["image_path"].startswith("/labels/Greek_Yogurt_")


@pytest.mark.asyncio
async def test_chat_endpoints():
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value={
        "message": "Processed recipe.",
        "image_path": "/labels/test.png",
        "exportable": {"type": "recipe_nutrition", "totals": {"calories": 100}},
        "artifacts": [{"type": "label_image", "image_path": "/labels/test.png"}],
    })

    async def mock_stream_events(message, thread_id):
        yield {"event": "token", "data": {"token": "Hello "}}
        yield {"event": "token", "data": {"token": "world!"}}
        yield {"event": "tool_end", "data": {"tool": "search_recipe_knowledge", "artifact": None}}
        yield {"event": "done", "data": {"message": "Hello world!", "thread_id": thread_id}}

    mock_agent.astream_events = mock_stream_events

    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user"}

    client = TestClient(app)

    # 1. Test POST /api/chat
    chat_resp = client.post("/api/chat", json={"message": "Analyze 1 cup milk"})
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["response"] == "Processed recipe."
    assert data["image_path"] == "/labels/test.png"
    assert data["exportable"]["totals"]["calories"] == 100
    assert len(data["artifacts"]) == 1

    # 2. Test POST /api/chat/stream
    stream_resp = client.post("/api/chat/stream", json={"message": "Stream milk"})
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]
    text_body = stream_resp.text
    assert "event: token" in text_body
    assert "event: tool_end" in text_body
    assert "event: done" in text_body

    app.dependency_overrides.clear()
