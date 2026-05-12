# 🇦🇱 Lahuta: Albanian LLM Ecosystem

Lahuta is a modular platform for developing, training, and serving specialized Albanian language models. It provides an end-to-end pipeline from synthetic data generation and programmatic augmentation to fine-tuning with Chain-of-Thought (CoT) and production-ready inference.

## 🏗️ Project Architecture

The project is structured to support multiple specialized models within a shared infrastructure.

- **`api/`**: A centralized FastAPI server that handles:
  - Dynamic model loading from HuggingFace Hub or local storage.
  - Multi-model state management.
  - SSE Streaming for real-time model responses.
  - Project-specific output validation and feedback collection (RLHF).
- **`models/`**: Independent directories for each specialized model:
  - `albanian_analysis/`: Structural, grammatical, and style editing.
  - `teacher_diary_generator/`: Structured generation for educational contexts.
- **`docs/`**: Technical specifications and architectural documentation.

## 🛠️ Getting Started

### 1. Prerequisites
- Python 3.10+
- `llama-cpp-python` (with hardware acceleration for local inference)
- API Keys for teacher models (Groq, Anthropic, or OpenAI)

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

## 🚀 Serving Models

The Lahuta API dynamically loads models based on `api/models_config.json`.

```bash
# Run the server
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Key Endpoints:
- `POST /analyze`: Main inference endpoint. Supports `"stream": true`.
- `POST /models/load`: Load a new model or update configuration at runtime.
- `GET /health`: Monitor loaded models and server uptime.
- `POST /feedback`: Collect user corrections for future DPO/RLHF training.

## 📊 Data Pipeline

Each model in `models/` contains its own data pipeline scripts:

1. **Generation**: `generate_synthetic.py` creates high-quality JSON scaffolds.
2. **Augmentation**: `augment.py` programmatically expands the dataset.
3. **Validation**: `validate_schema.py` ensures strict adherence to training schemas.
4. **Splitting**: `split_dataset.py` creates stratified train/val/test splits.

To run the pipeline for a specific model:
```bash
python models/albanian_analysis/scripts/run_pipeline.py
```

## 🧠 Training

Lahuta models are optimized for **Gemma 4:e4b** using Chain-of-Thought (CoT) reasoning traces. Training scripts and configurations are located in each model's `training/` directory.

---
*Lahuta - Empowering the Albanian language through advanced AI.*
