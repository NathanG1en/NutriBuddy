"""
FastAPI backend for Nutrition Agent
Run with: uvicorn backend.api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import uuid
from datetime import datetime
import asyncio


# ============================================
# FastAPI Setup
# ============================================

app = FastAPI(
    title="Nutrition Agent API",
    description="AI-powered nutrition label generation API",
    version="1.0.0"
)

# CORS for frontend (React, Vite, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite alternate port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Request/Response Models
# ============================================

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    image_path: Optional[str] = None  # Matches frontend expectation


class MessageHistory(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    image_path: Optional[str] = None


class HistoryResponse(BaseModel):
    thread_id: str
    message_count: int
    messages: List[MessageHistory]


class ToolInfo(BaseModel):
    name: str
    description: str


class ToolsResponse(BaseModel):
    count: int
    tools: List[ToolInfo]


class HealthResponse(BaseModel):
    status: str
    agent: str
    tools_count: int
    api_version: str


# ============================================
# In-memory storage (replace with DB in production)
# ============================================

conversation_store: dict[str, List[MessageHistory]] = {}


# ============================================
# API Endpoints
# ============================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Nutrition Agent API",
        "version": "1.0.0"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and receive an AI response.
    
    Returns example responses without actual AI implementation.
    """
    try:
        thread_id = request.thread_id or str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Initialize thread if needed
        if thread_id not in conversation_store:
            conversation_store[thread_id] = []
        
        # Store user message
        conversation_store[thread_id].append(MessageHistory(
            role="user",
            content=request.message,
            timestamp=timestamp,
            image_path=None
        ))
        
        # Generate example response based on message content
        user_msg_lower = request.message.lower()
        
        if any(word in user_msg_lower for word in ["avocado", "salmon", "chicken", "milk", "find", "search"]):
            response_text = f"I found nutritional information for your search! Here's a sample nutrition label I generated."
            # Example placeholder image URL - replace with real image service later
            image_path = "https://via.placeholder.com/300x400.png?text=Nutrition+Label"
        elif "label" in user_msg_lower or "generate" in user_msg_lower or "create" in user_msg_lower:
            response_text = "I've generated a nutrition label for you. You can see the label image below and download it."
            image_path = "https://via.placeholder.com/300x400.png?text=Nutrition+Label"
        elif "compare" in user_msg_lower:
            response_text = "Here's a comparison of the nutritional values:\n\n**Salmon (100g):**\n- Protein: 20g\n- Fat: 13g\n- Calories: 208\n\n**Chicken Breast (100g):**\n- Protein: 31g\n- Fat: 3.6g\n- Calories: 165\n\nChicken breast has more protein and fewer calories, while salmon provides healthy omega-3 fats!"
            image_path = None
        elif "hello" in user_msg_lower or "hi" in user_msg_lower:
            response_text = "Hello! I'm your nutrition assistant. I can help you search for foods in the USDA database and create nutrition labels. Try asking me to find a specific food!"
            image_path = None
        elif "help" in user_msg_lower:
            response_text = "I can help you with:\n\n🔍 **Search foods** - \"Find avocado\"\n📊 **Create labels** - \"Create a nutrition label for banana\"\n⚖️ **Compare foods** - \"Compare protein in salmon vs chicken\"\n\nJust ask away!"
            image_path = None
        else:
            response_text = "I can help you search for foods and create nutrition labels. Try asking something like \"Find avocado and create a nutrition label\" or \"Compare salmon and chicken breast\"!"
            image_path = None
        
        # Store assistant response
        conversation_store[thread_id].append(MessageHistory(
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow().isoformat(),
            image_path=image_path
        ))
        
        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            image_path=image_path
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream agent responses in real-time using Server-Sent Events.
    
    Example frontend usage:
    ```javascript
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Hello', thread_id: 'abc123' })
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        console.log(decoder.decode(value));
    }
    ```
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    
    async def event_generator():
        try:
            # Simulate streaming response
            example_response = "I'm analyzing your nutrition request. This is an example streaming response that would normally come from the AI agent."
            
            words = example_response.split()
            
            for i, word in enumerate(words):
                event_data = {
                    "type": "token",
                    "data": word + " ",
                    "thread_id": thread_id
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                await asyncio.sleep(0.1)  # Simulate typing delay
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/history/{thread_id}", response_model=HistoryResponse)
async def get_history(thread_id: str):
    """
    Get conversation history for a specific thread.
    """
    messages = conversation_store.get(thread_id, [])
    
    return HistoryResponse(
        thread_id=thread_id,
        message_count=len(messages),
        messages=messages
    )


@app.delete("/api/history/{thread_id}")
async def clear_history(thread_id: str):
    """
    Clear conversation history for a specific thread.
    """
    if thread_id in conversation_store:
        del conversation_store[thread_id]
        return {"status": "success", "message": f"History cleared for thread {thread_id}"}
    
    return {"status": "success", "message": "No history found for this thread"}


@app.get("/api/threads")
async def get_threads():
    """
    Get all active conversation threads.
    """
    threads = []
    for thread_id, messages in conversation_store.items():
        threads.append({
            "thread_id": thread_id,
            "message_count": len(messages),
            "last_activity": messages[-1].timestamp if messages else None
        })
    
    return {
        "count": len(threads),
        "threads": threads
    }


@app.post("/api/threads")
async def create_thread():
    """
    Create a new conversation thread.
    """
    thread_id = str(uuid.uuid4())
    conversation_store[thread_id] = []
    
    return {
        "thread_id": thread_id,
        "created_at": datetime.utcnow().isoformat()
    }


@app.get("/api/tools", response_model=ToolsResponse)
async def get_tools():
    """
    Get list of available agent tools.
    """
    # Example tools that would be available
    example_tools = [
        ToolInfo(
            name="generate_nutrition_label",
            description="Generate a nutrition facts label image from nutritional data"
        ),
        ToolInfo(
            name="search_food_database",
            description="Search for nutritional information of common foods"
        ),
        ToolInfo(
            name="calculate_daily_values",
            description="Calculate percentage daily values based on a 2000 calorie diet"
        ),
        ToolInfo(
            name="analyze_ingredients",
            description="Analyze a list of ingredients for nutritional content"
        ),
    ]
    
    return ToolsResponse(
        count=len(example_tools),
        tools=example_tools
    )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Detailed health check with service status.
    """
    return HealthResponse(
        status="healthy",
        agent="ready",
        tools_count=4,
        api_version="1.0.0"
    )


# ============================================
# Run with: uvicorn backend.api.main:app --reload --port 8000
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
