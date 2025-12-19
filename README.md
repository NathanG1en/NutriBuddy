## Welcome to NutriBuddy!
<img width="3020" height="1588" alt="image" src="https://github.com/user-attachments/assets/cc691613-d3ac-4cca-9980-9d73e4b3ba48" />



```
main.py

   │
   └──► Agent (graph.py)

           │
           └──► Tools (tools.py)  ──► Services (nutrition.py, labels.py)

```
## The Flow

1. **API receives request** → calls `agent.run(message)`
2. **Agent (LangGraph)** → LLM decides to call `search_foods` tool
3. **Tool** → calls `NutritionService.search()`
4. **Service** → hits USDA API, returns data
5. **Tool** → formats response for LLM
6. **Agent** → LLM processes result, maybe calls another tool or responds
7. **API** → returns response to frontend
