from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import os
import json
import time
import asyncio
import copy
from pathlib import Path
from dotenv import load_dotenv
import httpx
import db

# Load environment variables
repo_root = Path(__file__).parent.parent
load_dotenv(repo_root / ".env")

app = FastAPI(
    title="Lahuta Task Engine API",
    description="A flexible, multipurpose Albanian AI task engine. Supports dynamic system prompts, JSON schema enforcement, and RLHF feedback collection.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


# Security
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", os.environ.get("API_KEY"))
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validates API key against admin key or database."""
    if ADMIN_KEY and api_key_header == ADMIN_KEY:
        return {"id": 0, "username": "admin"}
    if api_key_header:
        user_info = db.verify_key(api_key_header)
        if user_info:
            return user_info
    if not ADMIN_KEY:
        return {"id": -1, "username": "anonymous"}
    raise HTTPException(status_code=403, detail="Could not validate API key")

# Global state
class ModelState:
    base_llm = None
    startup_time = time.time()

# Request Models
class AnalyzeRequest(BaseModel):
    task_id: str
    input_data: Dict[str, Any]
    stream: bool = False

class TaskUpsertRequest(BaseModel):
    id: str
    name: str
    system_prompt: str
    description: Optional[str] = None
    output_schema: Optional[Dict[str, Any]] = None

class RegisterRequest(BaseModel):
    username: str

class KeyRequest(BaseModel):
    name: Optional[str] = "default"

class FeedbackRequest(BaseModel):
    session_id: str
    task_id: str
    input_data: Dict[str, Any]
    model_output: Dict[str, Any]
    rating: str

# Model Initialization
async def initialize_base_model():
    """Load the single base model defined in .env."""
    from llama_cpp import Llama
    
    model_path = os.environ.get("BASE_MODEL_PATH")
    if not model_path:
        # Check common locations or use a default name
        potential_paths = [
            "models/gemma-4e2b-q4_k_m.gguf",
            "gemma-4e2b-q4_k_m.gguf"
        ]
        for p in potential_paths:
            if (repo_root / p).exists():
                model_path = p
                break
    
    if not model_path:
        print("WARNING: No base model found. API will run in mock mode or error on inference.")
        return

    abs_path = repo_root / model_path
    print(f"Loading Base LLM from {abs_path}...")
    try:
        ModelState.base_llm = Llama(
            model_path=str(abs_path),
            n_ctx=8192,
            n_threads=max(1, os.cpu_count() - 1)
        )
    except Exception as e:
        print(f"FAILED to load model: {e}")

@app.on_event("startup")
async def startup_event():
    await initialize_base_model()
    # Ensure a default task exists
    if not db.list_tasks():
        db.upsert_task(
            task_id="albanian_analysis",
            name="Albanian Content Analysis",
            system_prompt="You are an expert Albanian linguistic analyzer. Analyze the provided JSON content for grammar, structure, and style. Output valid JSON only.",
            description="Default analysis task for Albanian text."
        )

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "base_model_loaded": ModelState.base_llm is not None,
        "uptime_seconds": int(time.time() - ModelState.startup_time),
        "tasks": len(db.list_tasks())
    }

# Task Management
@app.get("/tasks")
def list_tasks():
    return db.list_tasks()

@app.post("/tasks")
async def add_task(req: TaskUpsertRequest, user_info: dict = Depends(get_api_key)):
    if user_info["id"] != 0:
        raise HTTPException(status_code=403, detail="Admin access required")
    db.upsert_task(req.id, req.name, req.system_prompt, req.description, req.output_schema)
    return {"status": "success", "task_id": req.id}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: str, user_info: dict = Depends(get_api_key)):
    if user_info["id"] != 0:
        raise HTTPException(status_code=403, detail="Admin access required")
    db.delete_task(task_id)
    return {"status": "success"}

# Auth
@app.post("/auth/register")
async def register(req: RegisterRequest):
    user_id = db.create_user(req.username)
    api_key = db.generate_key(user_id, name="initial_key")
    return {"status": "success", "username": req.username, "api_key": api_key}

@app.get("/auth/me")
async def get_me(user_info: dict = Depends(get_api_key)):
    return user_info

# Inference
@app.post("/analyze")
async def analyze(req: AnalyzeRequest, user_info: dict = Depends(get_api_key)):
    if not ModelState.base_llm:
        raise HTTPException(status_code=500, detail="Base LLM not loaded.")
        
    task = db.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    system_prompt = task["system_prompt"]
    input_json = json.dumps(req.input_data, indent=2, ensure_ascii=False)
    
    # Generic Prompt Template
    prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{input_json}\n<|assistant|>\n"
    
    if req.stream:
        async def event_generator():
            try:
                for output in ModelState.base_llm(prompt, max_tokens=2048, temperature=0.1, stop=["<end_of_turn>", "<|end|>"], stream=True):
                    token = output['choices'][0]['text']
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0.001)
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        response = ModelState.base_llm(prompt, max_tokens=2048, temperature=0.1, stop=["<end_of_turn>", "<|end|>"])
        response_text = response['choices'][0]['text'].strip()
        
        # Clean markdown if model outputted it
        if response_text.startswith("```json"):
            response_text = response_text[7:].strip()
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
            
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"raw": response_text, "parse_error": True}

# RLHF
@app.post("/feedback")
async def collect_feedback(req: FeedbackRequest, user_info: dict = Depends(get_api_key)):
    db.save_feedback(
        task_id=req.task_id,
        input_data=req.input_data,
        model_output=req.model_output,
        rating=req.rating,
        user_id=user_info["id"],
        session_id=req.session_id
    )
    return {"status": "success", "message": "Feedback saved."}

@app.get("/rlhf/stats")
def get_rlhf_stats():
    rows = db.get_feedback_stats()
    stats = {}
    for tid, rating, count in rows:
        if tid not in stats: stats[tid] = {}
        stats[tid][rating] = count
    return stats

@app.get("/rlhf/dashboard", response_class=HTMLResponse)
async def rlhf_dashboard():
    template_path = repo_root / "api" / "templates" / "rlhf_dashboard.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("Dashboard template not found.", status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
