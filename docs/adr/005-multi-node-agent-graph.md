# ADR 005: Multi-Node LangGraph Agent Architecture (Planner, Tools & Auditor)

* **Status**: Implemented / Accepted
* **Date**: October 2026
* **Deciders**: AI & Data Engineering Pair
* **Related Track**: Track 3 & Advanced Agent Capabilities

---

## Context

In earlier iterations of NutriBuddy's conversational assistant, a single-node ReAct loop (`agent` ↔ `tools`) handled all incoming requests. This single-agent structure suffered from several limitations:
1. **Conflicting Personas & Instruction Dilution**: The single prompt asked the model to be simultaneously an inviting, creative chef proposing tasty recipes and a rigorous registered dietitian screening for allergens, micronutrient deficiencies, and sodium limits. As prompt complexity grew, the model frequently truncated nutritional safety notes or omitted allergen screenings in favor of conversational fluff.
2. **Lack of Specialized Verification**: Recipes calculated from USDA FoodData Central were returned directly to the user without a secondary clinical evaluation of nutritional balance (e.g. excessive sodium >1,000mg, high added sugars, or unbalanced macronutrient ratios).
3. **Monolithic State**: Routing decisions were rigid and couldn't distinguish between lightweight informational lookups and multi-ingredient recipes requiring dietetic scrutiny.

---

## Decisions

### 1. Multi-Node StateGraph Decomposition
We decomposed the agent into a coordinated, multi-node LangGraph topology with distinct specialized personas:

```
                          ┌──────────────────────────┐
                          │   User Message Input     │
                          └─────────────┬────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │  Node 1: NutriChef       │
                          │  (Culinary Planner)      │
                          └─────────────┬────────────┘
                                        │
                         Tool Call?     │     No Tools (Direct Answer)
                  ┌─────────────────────┴──────────────────────┐
                  ▼                                            ▼
      ┌──────────────────────┐                                END
      │   Node 2: Tools      │
      │   (ToolNode)         │
      └───────────┬──────────┘
                  │
                  ▼
      ┌──────────────────────┐
      │  Node 1: NutriChef   │
      │  (Synthesizes Steps) │
      └───────────┬──────────┘
                  │
        Recipe / Meal Tool?
       (Dietetic Audit Needed)
                  │
                  ▼
      ┌──────────────────────┐
      │  Node 3: NutriAuditor│
      │  (Dietitian/Safety)  │
      └───────────┬──────────┘
                  │
                  ▼
                 END
```

#### Node 1: `planner` (`NutriChef`)
* **Role**: Primary culinary strategist and tool orchestrator.
* **Responsibilities**: Decomposes culinary requests, consults cookbooks via RAG, searches USDA foods, and initiates recipe nutrition calculations or label generation.
* **Tools Bound**: All 8 tools (`search_foods`, `get_nutrition`, `calculate_recipe_nutrition`, `parse_recipe_text`, `search_recipe_knowledge`, `format_nutrition_label`, `generate_label_image`, `analyze_food_image`).

#### Node 2: `tools` (`ToolNode`)
* **Role**: Deterministic tool execution environment returning structured data and artifacts.

#### Node 3: `auditor` (`NutriAuditor`)
* **Role**: Senior registered dietitian and food safety specialist.
* **Responsibilities**:
  - Reviews finalized recipe ingredients and USDA nutritional totals.
  - **Allergen Screening**: Explicitly checks and flags the 9 major FDA food allergens (Milk/Dairy, Eggs, Fish, Crustacean Shellfish, Tree Nuts, Peanuts, Wheat/Gluten, Soy, Sesame).
  - **Macro & Micronutrient Audit**: Evaluates caloric density, protein-to-carb ratios, saturated fats, fiber sufficiency, and sodium levels (>1,000mg/serving warnings).
  - **Dietetic Optimization**: Appends practical food science and nutritional enhancement tips.

### 2. Adaptive Routing Logic
* **Fast-Path for Simple Lookups**: Queries like *"How many calories in a peach?"* route from `planner` ➔ `tools` ➔ `planner` ➔ `END`, completing with zero extra latency or redundant auditing.
* **Deep-Path for Recipes & Meals**: When `calculate_recipe_nutrition` or `analyze_food_image` runs, `should_continue_planner` detects that nutritional calculations occurred and conditionally transitions execution to `auditor` before finalizing.

### 3. Response & Artifact Synthesis
* `NutritionAgent._extract_result` concatenates non-tool assistant messages across nodes (preserving both the chef's culinary instructions and the dietitian's safety audit).
* All typed artifacts (`recipe_nutrition`, `label_image`, `meal_vision`) remain accessible and preserved on state.

---

## Consequences & Impact

### Positive
* **Higher Clinical Rigor**: Every recipe or meal analysis automatically receives dedicated allergen screening and nutritional balance auditing.
* **Separation of Concerns**: The chef node focuses on flavor, authentic techniques, and cooking steps; the auditor node focuses strictly on dietetics and food safety.
* **Zero Latency Penalty on Simple Questions**: Simple USDA lookups bypass the auditor node completely.
* **Preserved Backwards Compatibility**: Synchronous `run()`, asynchronous `arun()`, and SSE streaming `astream_events()` work without API breakages.
