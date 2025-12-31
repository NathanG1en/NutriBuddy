from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List
import shutil
import os
import tempfile
from backend.dependencies import get_rag_service
from backend.api.security import get_current_user
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.config import settings

router = APIRouter()


# --- Data Models ---
class Ingredient(BaseModel):
    item: str
    quantity: str
    unit: str
    notes: str = ""


class Recipe(BaseModel):
    title: str
    description: str
    ingredients: List[Ingredient]
    instructions: List[str]
    science_notes: str = Field(
        description="Explanation of the food science concepts used"
    )


class GenerateRequest(BaseModel):
    prompt: str


# --- Endpoints ---


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service=Depends(get_rag_service),
):
    """Uploads a PDF or Text file to the knowledge base."""
    # Create temp file
    suffix = ".pdf" if file.filename.endswith(".pdf") else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Ingest
        file_type = "pdf" if suffix == ".pdf" else "text"
        num_chunks = service.ingest_file(tmp_path, file_type)
        return {
            "filename": file.filename,
            "chunks_added": num_chunks,
            "status": "success",
        }
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/generate", response_model=Recipe)
async def generate_recipe(
    request: GenerateRequest,
    current_user: dict = Depends(get_current_user),
    service=Depends(get_rag_service),
):
    """Generates a recipe based on the prompt and RAG context."""
    try:
        # 1. Retrieve Context
        docs = service.query(request.prompt)
        context_text = "\n\n".join([d.page_content for d in docs])

        # 2. Setup LLM Chain
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=settings.gemini_api_key,
            temperature=0.7,
        )
        parser = JsonOutputParser(pydantic_object=Recipe)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert food scientist and chef. Create a detailed recipe based on the user's request. "
                    "Use the provided Food Science Context to inform your ingredient choices and techniques. "
                    "Explain the science in the 'science_notes' field.\n\n"
                    "{format_instructions}",
                ),
                ("user", "Context:\n{context}\n\nRequest: {request}"),
            ]
        )

        chain = prompt | llm | parser

        # 3. Generate
        result = chain.invoke(
            {
                "request": request.prompt,
                "context": context_text,
                "format_instructions": parser.get_format_instructions(),
            }
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_knowledge(
    current_user: dict = Depends(get_current_user), service=Depends(get_rag_service)
):
    """Clears the entire knowledge base."""
    service.clear()
    return {"status": "cleared"}
