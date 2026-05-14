# RLHF / DPO Guide

## When to run DPO
Only after collecting >= 150 preference pairs in rlhf/dpo_pairs.jsonl.
Running earlier will overfit to noise.

## Preference pair collection (PWA side)
The PWA must log the following on each "unhelpful" feedback action:
- Full input (article, guidelines, key_points)
- Full model output JSON
- Which task section and issue index was flagged
- The feedback rating (unhelpful | too_vague | too_harsh)
- Timestamp and client_id

Write each feedback event as a JSON file to data/rlhf/collected/.

## Human-in-the-loop Improvement
If the automated teacher model (e.g., Claude/GPT) fails to provide a high-quality "chosen" response, the feedback is marked for human review in `data/rlhf/needs_human_improvement/`.

1. **Access the Dashboard**: Navigate to `/rlhf/dashboard` in your browser.
2. **Authenticate**: Enter your API key (generate one via `POST /auth/register` if needed).
3. **Review Tasks**: The "Pending Improvements" section lists outputs flagged as unhelpful.
4. **Correct**: Provide a better, clearer instruction in Albanian and click "Submit Correction".
5. **DPO Integration**: Resolving a task automatically appends a new pair to `rlhf/dpo_pairs.jsonl`.

## Running DPO

```bash
# 1. Process raw feedback into pairs
python rlhf/collect_preferences.py --teacher  # uses teacher model to improve chosen responses

# 2. Check pair count
wc -l rlhf/dpo_pairs.jsonl

# 3. Run DPO (requires GPU — rent if needed)
python -m trl dpo \
  --model_name_or_path training/final \
  --config rlhf/dpo_config.yaml \
  --dataset_path rlhf/dpo_pairs.jsonl

# 4. Re-export to GGUF (see docs/EXPORT.md)
```

## Cadence
Run a DPO cycle every 500 new preference pairs or every 3 months, whichever comes first.
