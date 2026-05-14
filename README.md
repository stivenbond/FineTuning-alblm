# 🇦🇱 Lahuta: Albanian LLM Ecosystem

Lahuta is a modular platform for developing, training, and serving specialized Albanian language models. It provides an end-to-end pipeline from synthetic data generation and programmatic augmentation to fine-tuning with Chain-of-Thought (CoT) and production-ready inference.

## 🏗️ Project Architecture

The project is structured to support multiple specialized models within a shared infrastructure.

- **`api/`**: A centralized FastAPI server that handles:
  - Dynamic model loading from HuggingFace Hub or local storage.
  - Multi-model state management.
  - Multi-user Authentication via hashed API keys (`lh_...`).
  - SSE Streaming for real-time model responses.
  - Project-specific output validation and RLHF Dashboard.

- **`models/`**: Independent directories for each specialized model.
- **`docs/`**: Comprehensive guides for data, training, and deployment.

## 📚 Documentation
- [Data Collection & Annotation](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/DATA_GUIDE.md)
- [RLHF & DPO Workflow](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/RLHF_GUIDE.md)
- [RLHF Dashboard Guide](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/DASHBOARD_GUIDE.md)
- [API Authentication & Keys](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/API_AUTH.md)
- [Model Export & GGUF](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/EXPORT.md)


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
- `POST /auth/register`: Register a new user and get an API key.
- `GET /rlhf/dashboard`: Access the human-in-the-loop improvement UI.
- `POST /models/load`: Load a new model or update configuration at runtime.
- `GET /health`: Monitor loaded models and server uptime.
- `POST /feedback`: Write each feedback event as a JSON file to data/rlhf/collected/.

## Human-in-the-loop Improvement
If the automated teacher model (e.g., Claude/GPT) fails to provide a high-quality "chosen" response, the feedback is marked for human review.

1. **Access the Dashboard**: Navigate to `/rlhf/dashboard` in your browser.
2. **Authenticate**: Enter your API key (generate one via `POST /auth/register` if needed).
3. **Review Tasks**: The "Pending Improvements" section lists outputs flagged as unhelpful.
4. **Correct**: Provide a better, clearer instruction in Albanian and click "Submit Correction".
5. **DPO Integration**: Resolving a task automatically appends a new pair to `rlhf/dpo_pairs.jsonl` for RLHF training.


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
