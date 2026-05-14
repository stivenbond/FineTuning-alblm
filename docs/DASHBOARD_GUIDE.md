# RLHF Dashboard & Human-in-the-loop Workflow

The Lahuta RLHF Dashboard is a specialized interface for improving model performance through human feedback.

## Accessing the Dashboard
1. Ensure the API server is running.
2. Navigate to `http://localhost:8000/rlhf/dashboard` in your browser.
3. Enter your **API Key** in the connection bar to load your tasks and statistics.

## The Feedback Loop
The dashboard facilitates the **RLHF (Reinforcement Learning from Human Feedback)** cycle:

1. **Inference**: A user (or PWA) calls `/analyze`.
2. **Feedback**: If the output is poor, the user submits feedback via `/feedback`.
3. **Teacher Filtering**: The background `collect_preferences.py` script attempts to fix the issue using a stronger teacher model (GPT-4o/Claude 3.5).
4. **Human Escalation**: If the teacher model cannot resolve the issue or isn't configured, the feedback is moved to the **Human Tasks** queue.
5. **Manual Correction**: An expert Albanian editor uses the dashboard to provide the "Chosen" response.
6. **DPO Dataset**: Once submitted, the pair is appended to `rlhf/dpo_pairs.jsonl` for final model fine-tuning.

## Dashboard Features

### 1. Stats Overview
Monitor the health of your RLHF pipeline:
- **DPO Ready**: The number of preference pairs ready for training.
- **Pending**: Tasks requiring immediate human attention.
- **Raw Feedback**: Total feedback items collected from end-users.

### 2. Resolution Interface
Each task shows:
- **Article Snippet**: The original context the model saw.
- **Rejected Guidance**: The exact text the model generated that was flagged as unhelpful.
- **Correction Box**: Where you enter the improved instruction.

> [!TIP]
> **Aesthetical Tip**: The dashboard uses a modern dark theme with glassmorphism. It is optimized for both desktop and tablet use for flexible annotation sessions.

## Training with Collected Data
Once you have collected a sufficient number of pairs (recommended: >= 150), follow the steps in [RLHF_GUIDE.md](file:///c:/Users/stive/Projects/Thesis/Lahuta/docs/RLHF_GUIDE.md) to initiate a DPO training run.
