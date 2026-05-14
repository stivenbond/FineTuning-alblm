from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field

from typing import List, Optional, Any, Dict
import os
import json
import time
import asyncio
import copy

import importlib.util
from pathlib import Path
import sys
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
import httpx
import auth



# Load environment variables
repo_root = Path(__file__).parent.parent
load_dotenv(repo_root / ".env")

app = FastAPI(title="Lahuta Model Ecosystem API")

# Security
API_KEY = os.environ.get("API_KEY")
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    # 1. Check legacy/master key from env
    if API_KEY and api_key_header == API_KEY:
        return {"id": 0, "username": "admin", "key_name": "legacy_env_key"}
    
    # 2. Check DB keys
    if api_key_header:
        user_info = auth.verify_key(api_key_header)
        if user_info:
            return user_info
        
    # 3. Allow access if no master key is set (development mode)
    if not API_KEY:
        return {"id": -1, "username": "anonymous", "key_name": "no_key_mode"}

    raise HTTPException(status_code=403, detail="Could not validate API key")


# Global state for Multi-Model Support
class ModelState:
    models = {}          # model_id -> Llama instance
    processors = {}      # model_id -> {build_prompt, parse_response, validate_and_repair}
    startup_time = time.time()
    last_inference = {}  # model_id -> timestamp
    ollama_models = set() # model_id
    config = {}


class AnalyzeRequest(BaseModel):
    model_id: str = "albanian_analysis"
    stream: bool = False
    # Allow any other fields for model-specific inputs
    model_config = {"extra": "allow"}

    def get_model_inputs(self) -> Dict[str, Any]:
        """Returns all fields except the infrastructure ones."""
        data = self.model_dump()
        data.pop("model_id", None)
        data.pop("stream", None)
        return data

class LoadModelRequest(BaseModel):
    model_id: str
    hf_repo_id: Optional[str] = None
    hf_filename: Optional[str] = None
    force_download: bool = False

class RegisterRequest(BaseModel):
    username: str

class KeyRequest(BaseModel):
    name: Optional[str] = "default"


class ResolveTaskRequest(BaseModel):
    model_id: str
    task_id: str
    chosen_guidance: str



class FeedbackRequest(BaseModel):
    session_id: str
    client_id: str
    input: Dict[str, Any]
    model_output: Dict[str, Any]
    feedback: Dict[str, Any]
    model_id: str = "albanian_analysis"

def load_processor(model_id: str, project_path: str):
    """Dynamically loads build_prompt and output_validator from the project's scripts folder."""
    scripts_dir = repo_root / project_path / "scripts"
    
    # Load build_prompt.py
    bp_path = scripts_dir / "build_prompt.py"
    if bp_path.exists():
        spec = importlib.util.spec_from_file_location(f"{model_id}.build_prompt", bp_path)
        bp_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bp_mod)
        ModelState.processors[model_id] = {
            "build_prompt": getattr(bp_mod, "build_prompt", None),
            "parse_response": getattr(bp_mod, "parse_response", None)
        }
    
    # Load output_validator.py
    ov_path = scripts_dir / "output_validator.py"
    if ov_path.exists():
        spec = importlib.util.spec_from_file_location(f"{model_id}.output_validator", ov_path)
        ov_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ov_mod)
        if model_id not in ModelState.processors:
            ModelState.processors[model_id] = {}
        ModelState.processors[model_id]["validate_and_repair"] = getattr(ov_mod, "validate_and_repair", None)

async def initialize_ollama_model(model_id: str, cfg: dict):
    """Checks if an Ollama model is available."""
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model_name = cfg.get("ollama_name", model_id)
    
    print(f"Checking Ollama for model {model_name}...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if model_name in models or any(m.startswith(f"{model_name}:") for m in models):
                    ModelState.ollama_models.add(model_id)
                    # Load project-specific logic if any
                    project_path = cfg.get("project_path")
                    if project_path:
                        load_processor(model_id, project_path)
                    return f"ollama://{model_name}"
            print(f"Ollama model {model_name} not found or Ollama unreachable.")
    except Exception as e:
        print(f"Ollama connection error: {e}")
    return None

async def initialize_model(model_id: str, cfg: dict):
    if cfg.get("backend") == "ollama":
        return await initialize_ollama_model(model_id, cfg)

    from llama_cpp import Llama

    
    hf_repo = cfg.get("hf_repo_id")
    hf_file = cfg.get("hf_filename")
    local_path = cfg.get("model_path")
    
    model_path = None
    
    if hf_repo and hf_file:
        print(f"Downloading {hf_file} from {hf_repo}...")
        try:
            model_path = hf_hub_download(
                repo_id=hf_repo,
                filename=hf_file,
                token=os.environ.get("HF_TOKEN")
            )
        except Exception as e:
            print(f"Failed to download from HF: {e}")
    
    if not model_path and local_path:
        # Fallback to local path relative to repo root
        abs_local_path = repo_root / local_path
        if abs_local_path.exists():
            model_path = str(abs_local_path)
    
    if not model_path:
        raise ValueError(f"No model file found for {model_id}")

    print(f"Loading Llama model from {model_path}...")
    ModelState.models[model_id] = Llama(
        model_path=model_path,
        n_ctx=cfg.get("n_ctx", 4096),
        n_threads=max(1, os.cpu_count() - 1)
    )
    
    # Load project-specific logic
    project_path = cfg.get("project_path")
    if project_path:
        load_processor(model_id, project_path)
    
    ModelState.last_inference[model_id] = None
    return model_path

@app.on_event("startup")
async def startup_event():
    config_path = os.environ.get("MODELS_CONFIG_PATH", str(repo_root / "api" / "models_config.json"))
    if not Path(config_path).exists():
        print(f"WARNING: Config file not found at {config_path}")
        return
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            ModelState.config = json.load(f)
            
        # We eagerly load models that have hf_repo_id or local paths
        for model_id, cfg in ModelState.config.items():
            try:
                await initialize_model(model_id, cfg)
                print(f"Model {model_id} initialized successfully.")
            except Exception as e:
                print(f"Could not auto-load {model_id}: {e}")
                
    except Exception as e:
        print(f"Error during startup: {e}")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "models_loaded": list(ModelState.models.keys()),
        "ollama_models": list(ModelState.ollama_models),
        "uptime_seconds": int(time.time() - ModelState.startup_time),
        "last_inference_timestamps": ModelState.last_inference
    }


@app.get("/models")
def list_models():
    """List all configured models and their status."""
    results = {}
    for mid, cfg in ModelState.config.items():
        results[mid] = {
            "name": cfg.get("name"),
            "description": cfg.get("description"),
            "loaded": mid in ModelState.models or mid in ModelState.ollama_models,
            "backend": cfg.get("backend", "llama_cpp"),
            "hf_repo": cfg.get("hf_repo_id"),
            "project_path": cfg.get("project_path")
        }

    return results

@app.post("/auth/register")
async def register(req: RegisterRequest):
    """Register a new user and return an initial API key."""
    user_id = auth.create_user(req.username)
    api_key = auth.generate_key(user_id, name="initial_key")
    return {"status": "success", "username": req.username, "api_key": api_key}

@app.post("/auth/keys")
async def create_key(req: KeyRequest, user_info: dict = Depends(get_api_key)):
    """Generate a new API key for the current user."""
    if user_info["id"] <= 0:
        raise HTTPException(status_code=400, detail="Cannot generate keys for special accounts")
    api_key = auth.generate_key(user_info["id"], name=req.name)
    return {"status": "success", "api_key": api_key}

@app.get("/auth/me")
async def get_me(user_info: dict = Depends(get_api_key)):
    """Return info about the current authenticated user."""
    return user_info


@app.post("/models/load")
async def load_model_on_fly(req: LoadModelRequest, api_key: str = Depends(get_api_key)):
    """Load or update a model configuration and model file at runtime."""
    model_id = req.model_id
    
    # Update config if provided
    if req.hf_repo_id and req.hf_filename:
        if model_id not in ModelState.config:
            ModelState.config[model_id] = {}
        ModelState.config[model_id]["hf_repo_id"] = req.hf_repo_id
        ModelState.config[model_id]["hf_filename"] = req.hf_filename
        
    if model_id not in ModelState.config:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not in configuration.")
    
    cfg = ModelState.config[model_id]
    try:
        path = await initialize_model(model_id, cfg)
        return {"status": "success", "model_id": model_id, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/models/{model_id}")
def unload_model(model_id: str, api_key: str = Depends(get_api_key)):
    """Unload a model from memory."""
    if model_id in ModelState.models:
        del ModelState.models[model_id]
        if model_id in ModelState.processors:
            del ModelState.processors[model_id]
        return {"status": "success", "message": f"Model {model_id} unloaded."}
    raise HTTPException(status_code=404, detail=f"Model {model_id} not loaded.")

@app.get("/schema/{model_id}")
def get_schema(model_id: str):
    cfg = ModelState.config.get(model_id)
    if not cfg or "project_path" not in cfg:
        raise HTTPException(status_code=404, detail="Model project not found")
        
    schema_path = repo_root / cfg["project_path"] / "schemas" / "training_example_v1.json"
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Schema not found")

@app.post("/analyze")
async def analyze(req: AnalyzeRequest, api_key: str = Depends(get_api_key)):
    model_id = req.model_id
    if model_id not in ModelState.models and model_id not in ModelState.ollama_models:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not loaded.")
        
    cfg = ModelState.config.get(model_id, {})
    backend = cfg.get("backend", "llama_cpp")
    
    if backend == "ollama":
        return await analyze_ollama(req, cfg)

    llm = ModelState.models[model_id]

    proc = ModelState.processors.get(model_id, {})
    cfg = ModelState.config.get(model_id, {})
    
    build_prompt_fn = proc.get("build_prompt")
    parse_response_fn = proc.get("parse_response")
    
    if not build_prompt_fn:
        raise HTTPException(status_code=500, detail=f"Processor 'build_prompt' missing for {model_id}")
    
    inputs = req.get_model_inputs()
    
    try:
        prompt = build_prompt_fn(**inputs)
    except TypeError as e:
        # Fallback for older processors that don't support **kwargs
        raise HTTPException(status_code=500, detail=f"Processor 'build_prompt' signature mismatch: {e}")
    
    ModelState.last_inference[model_id] = time.time()
    temperature = cfg.get("temperature", 0.1)

    if req.stream:
        async def event_generator():
            try:
                for output in llm(prompt, max_tokens=2048, temperature=temperature, stop=["<end_of_turn>"], stream=True):
                    token = output['choices'][0]['text']
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0.001)
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        response = llm(prompt, max_tokens=2048, temperature=temperature, stop=["<end_of_turn>"])
        response_text = response['choices'][0]['text']
        
        if parse_response_fn:
            parsed = parse_response_fn(response_text)
        else:
            parsed = {"raw": response_text}
        
        if parsed.get("parse_error"):
            return parsed
            
        validate_fn = proc.get("validate_and_repair")
        if validate_fn:
            repaired, _ = validate_fn(parsed, **inputs)
            return repaired
        return parsed

async def analyze_ollama(req: AnalyzeRequest, cfg: dict):
    model_id = req.model_id
    ollama_name = cfg.get("ollama_name", model_id)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    proc = ModelState.processors.get(model_id, {})
    build_prompt_fn = proc.get("build_prompt")
    parse_response_fn = proc.get("parse_response")
    
    inputs = req.get_model_inputs()
    
    # For Ollama models with custom Modelfiles, we often want to send raw data
    # to avoid duplicating the SYSTEM prompt defined in the Modelfile.
    if cfg.get("use_raw_input", True):
        prompt = json.dumps(inputs, indent=2, ensure_ascii=False)
    elif build_prompt_fn:
        prompt = build_prompt_fn(**inputs)
    else:
        # Fallback to simple prompt if no processor
        prompt = inputs.get("text") or inputs.get("prompt") or str(inputs)

    ModelState.last_inference[model_id] = time.time()
    temperature = cfg.get("temperature", 0.1)

    payload = {
        "model": ollama_name,
        "prompt": prompt,
        "stream": req.stream,
        "format": req.model_extra.get("format") if req.model_extra else None,
        "options": {"temperature": temperature}
    }
    
    # Remove format if None to avoid issues
    if payload["format"] is None and cfg.get("format"):
        payload["format"] = cfg.get("format")
    if payload["format"] is None:
        del payload["format"]

    if req.stream:
        async def event_generator():
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("POST", f"{ollama_host}/api/generate", json=payload) as response:
                        async for line in response.aiter_lines():
                            if line:
                                data = json.loads(line)
                                if "response" in data:
                                    yield f"data: {json.dumps({'token': data['response']})}\n\n"
                                if data.get("done"):
                                    break
                        yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"{ollama_host}/api/generate", json=payload)
            resp.raise_for_status()
            response_text = resp.json().get("response", "")
            
        if parse_response_fn:
            parsed = parse_response_fn(response_text)
        else:
            parsed = {"raw": response_text}
            
        validate_fn = proc.get("validate_and_repair")
        if validate_fn:
            repaired, _ = validate_fn(parsed, **inputs)
            return repaired
        return parsed


@app.post("/feedback")
async def collect_feedback(req: FeedbackRequest, api_key: str = Depends(get_api_key)):
    model_id = req.model_id
    cfg = ModelState.config.get(model_id)
    if not cfg or "project_path" not in cfg:
        raise HTTPException(status_code=404, detail="Model project for feedback not found")
        
    rlhf_dir = repo_root / cfg["project_path"] / "data" / "rlhf" / "collected"
    rlhf_dir.mkdir(parents=True, exist_ok=True)
    
    ts = int(time.time() * 1000)
    filename = f"{req.session_id}_{ts}.json"
    filepath = rlhf_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(req.dict(), f, indent=2, ensure_ascii=False)
        
    return {"status": "success", "message": "Feedback saved."}

@app.get("/rlhf/stats")
async def get_rlhf_stats(user_info: dict = Depends(get_api_key)):
    """Return stats about RLHF collection across all models."""
    stats = {}
    for model_id, cfg in ModelState.config.items():
        if "project_path" not in cfg: continue
        
        proj_path = repo_root / cfg["project_path"]
        collected_dir = proj_path / "data" / "rlhf" / "collected"
        human_dir = proj_path / "data" / "rlhf" / "needs_human_improvement"
        dpo_file = proj_path / "rlhf" / "dpo_pairs.jsonl"
        
        collected_count = len(list(collected_dir.glob("*.json"))) if collected_dir.exists() else 0
        human_count = len(list(human_dir.glob("*.json"))) if human_dir.exists() else 0
        
        dpo_count = 0
        if dpo_file.exists():
            try:
                with open(dpo_file, "r", encoding="utf-8") as f:
                    dpo_count = sum(1 for _ in f)
            except:
                pass
        
        stats[model_id] = {
            "collected": collected_count,
            "needs_human": human_count,
            "dpo_ready": dpo_count
        }
    return stats

@app.get("/rlhf/tasks")
async def list_rlhf_tasks(model_id: str = "albanian_analysis", user_info: dict = Depends(get_api_key)):
    """List pending tasks that need human improvement."""
    cfg = ModelState.config.get(model_id)
    if not cfg or "project_path" not in cfg:
        raise HTTPException(status_code=404, detail="Model project not found")
        
    human_dir = repo_root / cfg["project_path"] / "data" / "rlhf" / "needs_human_improvement"
    tasks = []
    if human_dir.exists():
        for filepath in human_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["id"] = filepath.name
                    tasks.append(data)
            except:
                continue
    return tasks

@app.post("/rlhf/tasks/resolve")
async def resolve_rlhf_task(req: ResolveTaskRequest, user_info: dict = Depends(get_api_key)):
    """Accept a human correction and move the task to the DPO dataset."""
    cfg = ModelState.config.get(req.model_id)
    if not cfg or "project_path" not in cfg:
        raise HTTPException(status_code=404, detail="Model project not found")
        
    proj_path = repo_root / cfg["project_path"]
    human_dir = proj_path / "data" / "rlhf" / "needs_human_improvement"
    dpo_file = proj_path / "rlhf" / "dpo_pairs.jsonl"
    task_file = human_dir / req.task_id
    
    if not task_file.exists():
        raise HTTPException(status_code=404, detail="Task not found")
        
    with open(task_file, "r", encoding="utf-8") as f:
        task_data = json.load(f)
        
    # Construct DPO pair
    chosen_out = copy.deepcopy(task_data["original_output"])
    task_name = task_data["task_name"]
    idx = task_data["issue_index"]
    
    # Update the guidance in the chosen output
    if task_name in chosen_out and "issues" in chosen_out[task_name]:
        issues = chosen_out[task_name]["issues"]
        if idx < len(issues):
            issues[idx]["guidance"] = req.chosen_guidance
    
    pair = {
        "input": task_data["input"],
        "chosen": chosen_out,
        "rejected": task_data["original_output"]
    }
    
    # Append to DPO file
    dpo_file.parent.mkdir(parents=True, exist_ok=True)
    with open(dpo_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        
    # Remove human task
    task_file.unlink()
    
    return {"status": "success", "message": "Task resolved and pair added to DPO dataset."}


@app.get("/rlhf/dashboard", response_class=HTMLResponse)
async def rlhf_dashboard():
    """Serve the RLHF Admin Dashboard."""
    template_path = repo_root / "api" / "templates" / "rlhf_dashboard.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("Dashboard template not found.", status_code=404)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
