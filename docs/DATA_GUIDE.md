# Data Collection and Annotation Guide

## File naming convention
All training examples follow: `alb-{register}-{NNNN}.json`
- register: editorial | informational | marketing | classical | mixed | aug
- NNNN: zero-padded 4-digit counter, unique across ALL files

## The no-rewriting rule
The single most important annotation rule:
> guidance fields must NEVER contain suggested replacement text.

BAD:  "Fjalia është e gjatë — shkruaje kështu: 'Produkti është i mirë.'"
GOOD: "Fjalia tejkalon 40 fjalë — konsidero ndarjen e saj në dy fjali më të shkurtra"

If an annotator writes replacement text, the example must be corrected before entering gold/.

## Annotation workflow
1. generate_synthetic.py → data/raw_synthetic/
2. Human reviewer opens raw_synthetic file
3. Reviewer corrects: wrong locations, wrong guidance tone, wrong severities
4. Reviewer sets metadata.annotator = "human_corrected_synthetic"
5. Reviewer sets metadata.reviewer = their name, metadata.reviewed_at = today
6. Reviewer runs validate_schema.py on the file
7. On pass: move to data/gold/{register}/
8. On fail: fix schema issues, re-validate, then move

## Adding a new client's brand guidelines
1. Copy schemas/brand_guidelines_template.json
2. Fill all fields for the client
3. Save to data/brand_guidelines/{client_id}.json
4. No retraining needed — injected at inference time
