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
