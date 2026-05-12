#!/usr/bin/env bash
# =============================================================================
# Albanian Editor AI — Workspace Setup Script
# Run once to scaffold the entire project structure + all spec files
# Usage: bash setup_workspace.sh
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${GREEN}[setup]${RESET} $1"; }
info() { echo -e "${CYAN}[info]${RESET}  $1"; }
warn() { echo -e "${YELLOW}[warn]${RESET}  $1"; }
header() { echo -e "\n${BOLD}━━━ $1 ━━━${RESET}"; }

# =============================================================================
# 1. DIRECTORY TREE
# =============================================================================
header "Creating directory tree"

dirs=(
  "data/seed/editorial"
  "data/seed/informational"
  "data/seed/marketing"
  "data/seed/classical"
  "data/seed/mixed"
  "data/raw_synthetic"
  "data/gold/editorial"
  "data/gold/informational"
  "data/gold/marketing"
  "data/gold/classical"
  "data/gold/mixed"
  "data/augmented"
  "data/rlhf/preference_pairs"
  "data/rlhf/collected"
  "schemas"
  "scripts"
  "training/configs"
  "training/checkpoints"
  "training/final"
  "rlhf"
  "evals/results"
  "inference"
  "docs"
  "prompts"
)

for d in "${dirs[@]}"; do
  mkdir -p "$ROOT/$d"
  log "Created $d/"
done

# =============================================================================
# 2. SCHEMAS
# =============================================================================
header "Writing schemas"

cat > "$ROOT/schemas/training_example_v1.json" << 'EOF'
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AlbanianEditorTrainingExample",
  "version": "1.0.0",
  "description": "Canonical schema for all training examples. Do not modify without bumping version.",
  "type": "object",
  "required": ["id", "metadata", "input", "output"],
  "properties": {
    "id": { "type": "string", "pattern": "^alb-[a-z]+-[0-9]{4}$" },
    "metadata": {
      "type": "object",
      "required": ["register", "annotator", "rlhf_eligible", "version"],
      "properties": {
        "register":       { "type": "string", "enum": ["editorial","informational","marketing","classical","mixed"] },
        "annotator":      { "type": "string", "enum": ["human","synthetic","human_corrected_synthetic"] },
        "rlhf_eligible":  { "type": "boolean" },
        "version":        { "type": "string" },
        "reviewer":       { "type": "string" },
        "reviewed_at":    { "type": "string", "format": "date" }
      }
    },
    "input": {
      "type": "object",
      "required": ["article_text"],
      "properties": {
        "brand_guidelines": { "type": "string", "description": "Client brand voice doc, injected at inference. Empty string if none." },
        "key_points":       { "type": "array", "items": { "type": "string" }, "description": "Original brief key points given to writer. Empty array if no brief was provided." },
        "article_text":     { "type": "string", "minLength": 100 }
      }
    },
    "output": {
      "type": "object",
      "required": ["grammar","writing_style","formatting","brand_compliance","marketing_compliance","structure"],
      "properties": {
        "grammar":             { "$ref": "#/definitions/guidanceTask" },
        "writing_style":       { "$ref": "#/definitions/styleTask" },
        "formatting":          { "$ref": "#/definitions/guidanceTask" },
        "brand_compliance":    { "$ref": "#/definitions/scoredTask" },
        "marketing_compliance":{ "$ref": "#/definitions/scoredTask" },
        "structure":           { "$ref": "#/definitions/structureTask" }
      }
    }
  },
  "definitions": {
    "issue": {
      "type": "object",
      "required": ["location","issue_type","guidance","severity"],
      "properties": {
        "location":   { "type": "string" },
        "issue_type": { "type": "string" },
        "guidance":   { "type": "string", "description": "MUST be instructional only — never rewrite the text, only tell the writer what kind of problem exists and where to look." },
        "severity":   { "type": "string", "enum": ["critical","major","minor"] }
      }
    },
    "guidanceTask": {
      "type": "object",
      "required": ["verdict","issues"],
      "properties": {
        "verdict": { "type": "string", "enum": ["pass","fail","partial"] },
        "issues":  { "type": "array", "items": { "$ref": "#/definitions/issue" } }
      }
    },
    "styleTask": {
      "allOf": [
        { "$ref": "#/definitions/guidanceTask" },
        {
          "properties": {
            "detected_register": { "type": "string", "enum": ["editorial","informational","marketing","classical","mixed"] },
            "expected_register": { "type": "string", "enum": ["editorial","informational","marketing","classical","mixed","unspecified"] }
          }
        }
      ]
    },
    "scoredTask": {
      "type": "object",
      "required": ["score","verdict","issues"],
      "properties": {
        "score":   { "type": "number", "minimum": 0, "maximum": 100 },
        "verdict": { "type": "string", "enum": ["pass","fail","partial"] },
        "issues":  { "type": "array", "items": { "$ref": "#/definitions/issue" } }
      }
    },
    "keyPointCoverage": {
      "type": "object",
      "required": ["key_point","covered","elaboration_quality"],
      "properties": {
        "key_point":           { "type": "string" },
        "covered":             { "type": "boolean" },
        "elaboration_quality": { "type": "string", "enum": ["thorough","adequate","shallow","missing"] }
      }
    },
    "structureTask": {
      "type": "object",
      "required": ["verdict","key_points_coverage","structure_type_detected","guidance"],
      "properties": {
        "verdict":               { "type": "string", "enum": ["pass","fail","partial","no_brief_provided"] },
        "key_points_coverage":   { "type": "array", "items": { "$ref": "#/definitions/keyPointCoverage" } },
        "structure_type_detected":{ "type": "string", "enum": ["linear","exponential","non-linear","unclear"] },
        "guidance":              { "type": "string" }
      }
    }
  }
}
EOF
log "schemas/training_example_v1.json"

cat > "$ROOT/schemas/brand_guidelines_template.json" << 'EOF'
{
  "_instructions": "Fill this template for each client. This document is injected as system prompt context at inference time. The more specific, the better brand compliance scoring will be.",
  "client_id": "client-slug",
  "client_name": "Client Full Name",
  "language": "sq",
  "tone_descriptors": ["profesional", "konciz", "miqësor"],
  "forbidden_phrases": ["shembulli i frazës së ndaluar"],
  "preferred_phrases": ["shembulli i frazës së preferuar"],
  "formality_level": "formal | semi-formal | informal",
  "target_audience": "Përshkrim i audiencës target",
  "sentence_length_preference": "short | medium | long | varied",
  "active_voice_required": true,
  "first_person_allowed": false,
  "exclamation_marks_allowed": false,
  "notes": "Çdo udhëzim shtesë specifik për markën"
}
EOF
log "schemas/brand_guidelines_template.json"

# =============================================================================
# 3. PROMPTS
# =============================================================================
header "Writing teacher model prompts"

cat > "$ROOT/prompts/generate_synthetic_editorial.txt" << 'EOF'
You are an expert Albanian language editor and NLP data annotator.

Your task is to generate a training example for a multi-task Albanian text analysis model.
The output must be a single valid JSON object matching the schema exactly — no preamble, no markdown, no explanation.

## Task
Given the Albanian article below, produce a realistic editorial review as if you were a senior Albanian editor.
The review must identify real linguistic and structural issues present in the article.
Guidance text must be instructional only — never rewrite or suggest replacement text.
All text in the "guidance" and "issue_type" fields must be in Albanian.

## Register
editorial

## Brand Guidelines
{brand_guidelines}

## Key Points (original brief given to writer)
{key_points}

## Article
{article_text}

## Output Schema (produce this exactly)
{schema}

## Critical Rules
1. guidance fields: tell the writer WHAT is wrong and WHERE to look — never HOW to rewrite it
2. If the article has no issues for a task, set verdict to "pass" and issues to []
3. structure.verdict must be "no_brief_provided" if key_points is empty
4. All score values must be between 0 and 100
5. Severity calibration: critical=blocks publication, major=requires revision, minor=polish only
6. Output ONLY the JSON object. No other text.
EOF
log "prompts/generate_synthetic_editorial.txt"

for register in informational marketing classical mixed; do
cat > "$ROOT/prompts/generate_synthetic_${register}.txt" << EOF
You are an expert Albanian language editor and NLP data annotator.

Your task is to generate a training example for a multi-task Albanian text analysis model.
The output must be a single valid JSON object matching the schema exactly — no preamble, no markdown, no explanation.

## Task
Given the Albanian article below, produce a realistic editorial review as if you were a senior Albanian editor.
The review must identify real linguistic and structural issues present in the article.
Guidance text must be instructional only — never rewrite or suggest replacement text.
All text in the "guidance" and "issue_type" fields must be in Albanian.

## Register
${register}

## Brand Guidelines
{brand_guidelines}

## Key Points (original brief given to writer)
{key_points}

## Article
{article_text}

## Output Schema (produce this exactly)
{schema}

## Critical Rules
1. guidance fields: tell the writer WHAT is wrong and WHERE to look — never HOW to rewrite it
2. If the article has no issues for a task, set verdict to "pass" and issues to []
3. structure.verdict must be "no_brief_provided" if key_points is empty
4. All score values must be between 0 and 100
5. Severity calibration: critical=blocks publication, major=requires revision, minor=polish only
6. Output ONLY the JSON object. No other text.
EOF
log "prompts/generate_synthetic_${register}.txt"
done

# =============================================================================
# 4. SCRIPT SPECS
# =============================================================================
header "Writing script specs"

cat > "$ROOT/scripts/SPECS.md" << 'EOF'
# Script Specifications
All scripts live in `scripts/`. Each section below is a spec for one script.
Implement them in order — later scripts depend on earlier ones.

---

## 1. validate_schema.py

**Purpose:** Validate every JSONL training example against `schemas/training_example_v1.json`.
Reject malformed examples before they enter the training pipeline.
Must be runnable as a pre-commit hook and as a CI step.

**Inputs:**
- `--input`  Path to a `.jsonl` file or a directory of `.jsonl` files
- `--schema` Path to schema JSON (default: `schemas/training_example_v1.json`)
- `--fix`    Optional flag: attempt to auto-fix common issues (missing empty arrays, wrong verdict casing)
- `--strict` Optional flag: fail on any warning, not just errors

**Outputs:**
- Stdout: per-file summary — total / valid / invalid / fixed
- `--report` Optional path to write a JSON report of all failures with line numbers
- Exit code 0 if all valid, 1 if any invalid after fix attempts

**Validation rules (in order):**
1. JSON parses without error
2. All required top-level fields present: id, metadata, input, output
3. `id` matches pattern `alb-[a-z]+-[0-9]{4}`
4. `metadata.register` is one of the 5 allowed values
5. `metadata.annotator` is one of the 3 allowed values
6. `input.article_text` length >= 100 characters
7. All 6 output task sections present
8. For scored tasks: `score` is number 0–100
9. For structure task: if `input.key_points` is empty, `verdict` must be `no_brief_provided`
10. All `guidance` fields: must not contain quoted text blocks (regex: no text wrapped in «» or "")
    — this enforces the no-rewriting rule at the data level
11. All `severity` values are one of: critical, major, minor
12. No issue has an empty `guidance` string

**Dependencies:** `jsonschema`, `argparse`, `re`, `pathlib`

---

## 2. generate_synthetic.py

**Purpose:** Call a teacher model API (Anthropic Claude or OpenAI GPT-4o) to generate
synthetic training examples from seed articles. Outputs raw unreviewed JSONL
to `data/raw_synthetic/`.

**Inputs:**
- `--seed-dir`    Path to directory of seed `.txt` articles (default: `data/seed/`)
- `--register`    Which register to process: editorial|informational|marketing|classical|mixed|all
- `--model`       Teacher model: `claude-opus-4-5` or `gpt-4o` (default: claude)
- `--per-article` How many synthetic variants to generate per seed article (default: 3)
- `--guidelines`  Path to a brand guidelines JSON to inject (optional)
- `--key-points`  Path to a `.txt` file with one key point per line (optional)
- `--output-dir`  Output directory (default: `data/raw_synthetic/`)
- `--dry-run`     Print prompts but do not call API

**Process per seed article:**
1. Load seed article text
2. Load prompt template from `prompts/generate_synthetic_{register}.txt`
3. Inject article, brand_guidelines, key_points, schema into template
4. Call teacher model API with temperature 0.8 (varied outputs)
5. Attempt JSON parse of response
6. If parse fails: retry once with temperature 0.3 and explicit JSON repair prompt
7. If parse still fails: log to `data/raw_synthetic/failed/` with error, skip
8. Run validate_schema on output — if invalid, log warning but still save (for human review)
9. Write to `data/raw_synthetic/{register}/alb-{register}-{NNNN}.json`
10. Maintain a counter file so IDs never collide across runs

**ID generation:** Read current max ID from counter file, increment, zero-pad to 4 digits.

**Rate limiting:** Respect API rate limits — add configurable `--delay` between calls (default 1s).

**Dependencies:** `anthropic` or `openai`, `argparse`, `json`, `pathlib`, `time`, `logging`

---

## 3. augment.py

**Purpose:** Programmatically expand the gold dataset without requiring human annotation.
Takes gold examples and produces new variants with controlled modifications.
Target ratio: 6–8 augmented examples per gold example.

**Inputs:**
- `--gold-dir`   Path to gold data directory (default: `data/gold/`)
- `--output-dir` Output directory (default: `data/augmented/`)
- `--strategy`   Comma-separated list of strategies to apply (default: all)
- `--seed`       Random seed for reproducibility (default: 42)

**Augmentation strategies (implement each as a separate function):**

`error_injection` — Take a pass/no-issues example. Programmatically inject one error:
  - Randomly remove punctuation from one sentence
  - Swap paragraph order
  - Remove capitalization from proper nouns (regex-based for Albanian)
  - Update the output to reflect the new injected error with an appropriate issue entry.
  - Severity: always inject as "minor" unless specified

`register_swap` — Swap the brand_guidelines between two examples of different registers.
  Update `metadata.register` and expected_register in writing_style accordingly.
  This teaches the model to discriminate brand voice from content.

`key_points_removal` — Take a structure:pass example.
  Remove all key_points from input.
  Set structure.verdict to "no_brief_provided" and clear key_points_coverage.
  Teaches the model the no-brief code path.

`severity_rebalance` — For examples with only minor issues, clone and upgrade
  one issue to major severity. Update verdict from pass to partial if needed.
  Improves class balance across severity levels.

`guidance_paraphrase` — For gold examples, call teacher model with low temperature
  to produce a semantically equivalent but lexically different guidance string.
  Adds lexical diversity without changing meaning.
  Only run this strategy if `--teacher-api-key` is set.

**Output naming:** `alb-aug-{strategy}-{NNNN}.json`

**Constraint:** Augmented examples must still pass validate_schema. Run validator
before writing each augmented example. Skip and log if it fails.

**Dependencies:** `re`, `random`, `copy`, `pathlib`, `json`, plus optionally `anthropic`/`openai` for guidance_paraphrase

---

## 4. split_dataset.py

**Purpose:** Produce stratified train/val/test splits from the combined
gold + augmented dataset. Stratification ensures proportional representation
of all registers and all severity levels in every split.

**Inputs:**
- `--gold-dir`      Path to gold data (default: `data/gold/`)
- `--augmented-dir` Path to augmented data (default: `data/augmented/`)
- `--output-dir`    Where to write splits (default: `data/splits/`)
- `--train`         Train fraction (default: 0.80)
- `--val`           Val fraction (default: 0.10)
- `--test`          Test fraction (default: 0.10)
- `--seed`          Random seed (default: 42)
- `--gold-only-test` Flag: ensure test set contains ONLY gold (human-reviewed) examples

**Stratification keys:**
- `metadata.register` (5 values)
- Dominant severity in the example: max severity across all issues
  (critical > major > minor > none)

**Process:**
1. Load all examples from both directories
2. Run validate_schema on all — skip invalids with warning
3. Build stratification groups as (register × dominant_severity) tuples
4. For each group, split proportionally
5. Enforce `--gold-only-test`: move any synthetic examples from test to train
6. Write `train.jsonl`, `val.jsonl`, `test.jsonl` to output dir
7. Print and save a split report: counts per register per severity per split

**Output files:**
- `data/splits/train.jsonl`
- `data/splits/val.jsonl`
- `data/splits/test.jsonl`
- `data/splits/split_report.json`

**Dependencies:** `sklearn.model_selection.StratifiedShuffleSplit` or manual implementation, `collections`, `pathlib`, `json`

---

## 5. build_prompt.py

**Purpose:** Convert a training example's `input` block into the exact
instruction-format prompt string that will be fed to Gemma during training
and inference. This is the single source of truth for prompt format.
Both the training pipeline and the inference server import this module.

**Interface (importable module + CLI):**

```python
def build_prompt(
    article_text: str,
    brand_guidelines: str = "",
    key_points: list[str] = [],
    register_hint: str = ""
) -> str:
    ...

def parse_response(response_text: str) -> dict:
    # Extract and parse the JSON from model output
    # Handle common malformations: trailing commas, missing braces
    ...
```

**Prompt structure to produce:**
```
<start_of_turn>system
Je një redaktor ekspert i gjuhës shqipe. Analizon artikujt dhe prodhon vlerësime të strukturuara JSON.
Rregull kritik: fushat "guidance" duhet të jenë vetëm udhëzuese — kurrë mos rishkruaj tekstin.
{brand_guidelines_section}
<end_of_turn>
<start_of_turn>user
{key_points_section}

## Artikulli për Analizë
{article_text}

Prodhoni analizën e plotë JSON për të 6 detyrat.
<end_of_turn>
<start_of_turn>model
```

**brand_guidelines_section:** If brand_guidelines is non-empty:
  `"## Udhëzimet e Markës\n{brand_guidelines}"`
  Else: empty string.

**key_points_section:** If key_points non-empty:
  `"## Pikat Kryesore të Briefit\n" + newline-joined numbered list`
  Else: `"## Pikat Kryesore\nAsnjë brief nuk është dhënë."` 

**parse_response:** 
  1. Try direct json.loads
  2. If fails: extract first `{...}` block with balanced brace matching
  3. If fails: strip trailing commas with regex, retry
  4. If fails: return {"parse_error": true, "raw": response_text}

**CLI usage:** `python build_prompt.py --example data/gold/editorial/alb-editorial-0001.json`
  Prints the assembled prompt to stdout for inspection.

**Dependencies:** `json`, `re`, `argparse`, `pathlib`

---

## 6. per_task_metrics.py (evals/)

**Purpose:** Evaluate model outputs on the test set across all 6 tasks.
Produces per-task metrics and an overall score card.

**Inputs:**
- `--predictions` Path to JSONL file of model predictions
- `--ground-truth` Path to JSONL file of ground truth (matched by `id`)
- `--output`       Path to write metrics JSON (default: `evals/results/{timestamp}.json`)

**Metrics per task:**

Grammar, writing_style, formatting (guidance tasks):
- Verdict accuracy: % correct verdict (pass/fail/partial)
- Issue count MAE: mean absolute error between predicted and true issue count
- Severity distribution match: KL divergence between predicted/true severity distributions

Brand_compliance, marketing_compliance (scored tasks):
- Score MAE: mean absolute error on 0–100 score
- Score correlation: Pearson r between predicted and true scores
- Verdict accuracy

Structure task:
- Verdict accuracy
- Key point coverage recall: % of truly covered points correctly identified as covered
- Key point coverage precision
- Structure type accuracy

Global:
- JSON validity rate: % of predictions that parsed as valid JSON
- Schema compliance rate: % that passed validate_schema
- Full-pass rate: % where ALL 6 task verdicts match ground truth

**Output:** JSON with per-task metrics dict + global metrics dict + per-example breakdown.

**Dependencies:** `numpy`, `scipy.stats`, `sklearn.metrics`, `json`, `pathlib`

---

## 7. json_validity_rate.py (evals/)

**Purpose:** Standalone fast check of raw model output files.
Run this before per_task_metrics to quickly catch model regression.

**Inputs:**
- `--predictions` Path to JSONL of raw model outputs (pre-parse)
- `--strict`       Also run validate_schema, not just json.loads

**Outputs:** Prints validity rate, lists first 10 failures with error messages.
Exit code 1 if validity rate < 0.90 (configurable with `--threshold`).

**Dependencies:** `json`, `jsonschema`, `argparse`

---

## 8. inference/server.py

**Purpose:** FastAPI server. Loads the quantized GGUF model once at startup.
Accepts article analysis requests, returns combined 6-task JSON.

**Endpoints:**

`POST /analyze`
  Request body:
  ```json
  {
    "article_text": "...",
    "brand_guidelines": "...",
    "key_points": ["..."],
    "client_id": "optional-for-logging"
  }
  ```
  Response: full 6-task output JSON (validated against schema before return)
  On validation failure: return 200 with `{"parse_error": true, "raw": "..."}` — never 500

`GET /health`
  Returns model load status, uptime, last inference timestamp

`GET /schema`
  Returns the current output schema for PWA integration reference

**Model loading:**
  On startup: load GGUF model from path in `ALBANIAN_EDITOR_MODEL_PATH` env var.
  Use `llama-cpp-python` library for inference.
  Set `n_ctx=4096` (sufficient for articles up to ~2000 words + guidelines).
  Set `n_threads` to CPU core count - 1.

**Request pipeline:**
  1. Validate request body (Pydantic)
  2. Call `build_prompt.build_prompt()` to assemble prompt
  3. Call model inference with `max_tokens=2048`, `temperature=0.1` (deterministic scoring)
  4. Call `build_prompt.parse_response()` to extract JSON
  5. Call `output_validator.validate_and_repair()` to enforce schema
  6. Log request + response (without article text if `LOG_ARTICLES=false`)
  7. Return response

**Dependencies:** `fastapi`, `uvicorn`, `llama-cpp-python`, `pydantic`

---

## 9. inference/output_validator.py

**Purpose:** Validate and repair model output JSON before returning to PWA.
The model will occasionally produce malformed JSON — this is the safety net.

**Interface:**
```python
def validate_and_repair(raw: dict) -> tuple[dict, list[str]]:
    # Returns (repaired_dict, list_of_repairs_made)
    # Raises OutputValidationError if unrepairable
```

**Repair rules (in order, stop after successful repair):**
1. Missing task key → inject empty scaffold for that task with verdict "fail" and issues []
2. Score out of range → clamp to 0–100
3. Invalid verdict string → map closest string match (e.g. "passed" → "pass")
4. Issue missing severity → default to "minor"
5. Issue missing guidance → set to "Shih seksionin përkatës për detaje." (placeholder)
6. structure.verdict not "no_brief_provided" when key_points was empty → force correct value
7. If more than 3 repairs were needed → flag response with `"low_confidence": true`

**Dependencies:** `pydantic`, `difflib` (for fuzzy verdict matching), `logging`

---

## 10. rlhf/collect_preferences.py

**Purpose:** Process raw preference feedback collected from PWA into
DPO-ready training pairs. Run periodically (e.g., weekly cron).

**Inputs:**
- `--raw-dir`    Directory of raw feedback JSON from PWA (default: `data/rlhf/collected/`)
- `--output`     Output JSONL path (default: `rlhf/dpo_pairs.jsonl`)
- `--min-pairs`  Minimum pairs before writing (default: 150)
- `--teacher`    If set, use teacher model to generate improved "chosen" responses

**Raw feedback format (from PWA):**
```json
{
  "session_id": "...",
  "client_id": "...",
  "input": { "...same as training input..." },
  "model_output": { "...full 6-task output..." },
  "feedback": {
    "task": "grammar | writing_style | ...",
    "issue_index": 2,
    "rating": "helpful | unhelpful | too_vague | too_harsh",
    "timestamp": "ISO8601"
  }
}
```

**Process:**
1. Load all raw feedback files
2. Group by (input_hash, task, issue_index)
3. Filter: keep only issues rated "unhelpful"/"too_vague"/"too_harsh"
4. For each filtered issue: produce a rejected output (the model's original)
5. If --teacher: call teacher model to produce improved guidance for that issue
   Else: flag for human improvement (write to `data/rlhf/needs_human_improvement/`)
6. Assemble DPO pair: {input, chosen (improved), rejected (original)}
7. Write to output JSONL, append-only
8. Print stats: total pairs, pairs by task, pairs needing human improvement

**Dependencies:** `hashlib`, `anthropic` or `openai` (optional), `json`, `pathlib`
EOF
log "scripts/SPECS.md"

# =============================================================================
# 5. TRAINING CONFIGS
# =============================================================================
header "Writing training configs"

cat > "$ROOT/training/configs/lora_config.yaml" << 'EOF'
# LoRA Configuration for Gemma 4
# Target: single adapter, all 6 tasks jointly
# Adjust rank up if val loss plateaus before epoch 3

model_name_or_path: "google/gemma-4-1b-it"   # start here; upgrade to 4b if needed
load_in_4bit: true                             # QLoRA — required for small training GPU

lora:
  r: 16                        # rank — increase to 32 if task diversity requires
  lora_alpha: 32               # scale = alpha/r, keep 2x rank
  lora_dropout: 0.05
  bias: "none"
  target_modules:              # Gemma attention projections
    - "q_proj"
    - "v_proj"
    - "k_proj"
    - "o_proj"
  task_type: "CAUSAL_LM"

# After training: merge adapter into base before GGUF export
# python -c "from peft import PeftModel; ..."  — see docs/EXPORT.md
EOF
log "training/configs/lora_config.yaml"

cat > "$ROOT/training/configs/training_args.yaml" << 'EOF'
# Training Arguments
output_dir: "training/checkpoints"
num_train_epochs: 5
per_device_train_batch_size: 2
gradient_accumulation_steps: 16   # effective batch = 32
learning_rate: 2.0e-4
lr_scheduler_type: "cosine"
warmup_ratio: 0.05
weight_decay: 0.01
fp16: false
bf16: true                         # use bf16 if GPU supports it (A100 yes, T4 no)
logging_steps: 10
eval_strategy: "steps"
eval_steps: 50
save_strategy: "steps"
save_steps: 100
save_total_limit: 3               # keep only last 3 checkpoints
load_best_model_at_end: true
metric_for_best_model: "eval_json_validity_rate"
greater_is_better: true
dataloader_num_workers: 2
remove_unused_columns: false
report_to: "none"                  # set to "wandb" if you want experiment tracking

# Early stopping — add EarlyStoppingCallback in training script
early_stopping_patience: 3        # stop if no improvement for 3 eval steps
EOF
log "training/configs/training_args.yaml"

cat > "$ROOT/rlhf/dpo_config.yaml" << 'EOF'
# DPO Configuration
# Run only after collecting >= 150 preference pairs

model_name_or_path: "training/final"    # start from the supervised fine-tuned model
beta: 0.1                               # KL penalty — lower = more aggressive preference learning
learning_rate: 5.0e-5                   # lower than SFT — DPO is sensitive
num_train_epochs: 1                     # 1 epoch is usually enough for DPO
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
max_length: 4096
max_prompt_length: 2048
output_dir: "training/dpo_checkpoints"
EOF
log "rlhf/dpo_config.yaml"

# =============================================================================
# 6. DOCS
# =============================================================================
header "Writing documentation"

cat > "$ROOT/docs/EXPORT.md" << 'EOF'
# Exporting to GGUF for CPU Deployment

## Step 1: Merge LoRA adapter into base model
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("google/gemma-4-1b-it")
model = PeftModel.from_pretrained(base, "training/final")
merged = model.merge_and_unload()
merged.save_pretrained("training/merged")
AutoTokenizer.from_pretrained("google/gemma-4-1b-it").save_pretrained("training/merged")
```

## Step 2: Convert to GGUF
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && pip install -r requirements.txt
python convert_hf_to_gguf.py ../training/merged --outfile ../training/final/albanian-editor.gguf
```

## Step 3: Quantize to Q4_K_M (best quality/size tradeoff for CPU)
```bash
./llama-quantize ../training/final/albanian-editor.gguf \
                 ../training/final/albanian-editor-q4km.gguf Q4_K_M
```

## Step 4: Test on CPU
```bash
./llama-cli -m ../training/final/albanian-editor-q4km.gguf \
            -p "$(cat test_prompt.txt)" \
            --temp 0.1 -n 2048
```

## Expected file sizes
- 1B model Q4_K_M: ~700MB
- 4B model Q4_K_M: ~2.5GB

## Expected CPU inference times (per ~500 word article)
- 1B Q4_K_M on 8-core CPU: ~8–15 seconds
- 4B Q4_K_M on 8-core CPU: ~25–45 seconds
EOF
log "docs/EXPORT.md"

cat > "$ROOT/docs/DATA_GUIDE.md" << 'EOF'
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
EOF
log "docs/DATA_GUIDE.md"

cat > "$ROOT/docs/RLHF_GUIDE.md" << 'EOF'
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
EOF
log "docs/RLHF_GUIDE.md"

# =============================================================================
# 7. PLACEHOLDER SCRIPTS (importable stubs)
# =============================================================================
header "Writing script stubs"

for script in validate_schema generate_synthetic augment split_dataset build_prompt; do
cat > "$ROOT/scripts/${script}.py" << EOF
"""
${script}.py — See scripts/SPECS.md for full specification.
This is a stub. Implement according to spec before running the pipeline.
"""
# TODO: implement per SPECS.md section for ${script}
raise NotImplementedError("Implement ${script} per SPECS.md before use.")
EOF
log "scripts/${script}.py"
done

for script in per_task_metrics json_validity_rate; do
cat > "$ROOT/evals/${script}.py" << EOF
"""
${script}.py — See scripts/SPECS.md for full specification.
"""
raise NotImplementedError("Implement ${script} per SPECS.md.")
EOF
log "evals/${script}.py"
done

for script in server output_validator; do
cat > "$ROOT/inference/${script}.py" << EOF
"""
${script}.py — See scripts/SPECS.md for full specification.
"""
raise NotImplementedError("Implement ${script} per SPECS.md.")
EOF
log "inference/${script}.py"
done

cat > "$ROOT/rlhf/collect_preferences.py" << 'EOF'
"""
collect_preferences.py — See scripts/SPECS.md for full specification.
"""
raise NotImplementedError("Implement collect_preferences per SPECS.md.")
EOF
log "rlhf/collect_preferences.py"

# =============================================================================
# 8. REQUIREMENTS + .gitignore + README
# =============================================================================
header "Writing requirements and project files"

cat > "$ROOT/requirements.txt" << 'EOF'
# Data pipeline
jsonschema>=4.21.0
anthropic>=0.30.0
openai>=1.35.0
pyyaml>=6.0.1

# Training
torch>=2.3.0
transformers>=4.42.0
peft>=0.11.0
trl>=0.9.0
bitsandbytes>=0.43.0
datasets>=2.20.0
accelerate>=0.31.0

# Evaluation
numpy>=1.26.0
scipy>=1.13.0
scikit-learn>=1.5.0

# Inference server
fastapi>=0.111.0
uvicorn>=0.30.0
llama-cpp-python>=0.2.80
pydantic>=2.7.0
EOF
log "requirements.txt"

cat > "$ROOT/.gitignore" << 'EOF'
# Data — never commit raw articles or model weights to git
data/seed/
data/raw_synthetic/
data/gold/
data/augmented/
data/rlhf/

# Model artifacts
training/checkpoints/
training/final/
*.gguf
*.bin
*.safetensors

# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/

# Secrets
.env
*.key

# OS
.DS_Store
Thumbs.db

# Logs
*.log
evals/results/

# Keep schema, prompts, specs, configs in git — these define the project
EOF
log ".gitignore"

cat > "$ROOT/README.md" << 'EOF'
# Albanian Editor AI

Multi-task Albanian text analysis model. Performs 6 editorial checks in a
single inference pass and returns a combined JSON result.

## Tasks
1. **Grammar** — morphosyntactic compliance
2. **Writing Style** — register detection and consistency
3. **Formatting** — paragraphing and punctuation
4. **Brand Compliance** — scored against injected client guidelines
5. **Marketing Compliance** — scored against marketing best practices
6. **Structure** — key point coverage and elaboration linearity

## Quick Start
```bash
# 1. Set up workspace (already done if you ran setup_workspace.sh)
bash setup_workspace.sh

# 2. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Read the data guide before doing anything else
cat docs/DATA_GUIDE.md
```

## Pipeline Order
```
seed articles
    ↓
scripts/generate_synthetic.py    # generate raw training data
    ↓
[human review → data/gold/]      # most critical step
    ↓
scripts/augment.py               # expand to 2000+ examples
    ↓
scripts/validate_schema.py       # gate check before training
    ↓
scripts/split_dataset.py         # train/val/test splits
    ↓
[training — see training/configs/]
    ↓
[GGUF export — see docs/EXPORT.md]
    ↓
inference/server.py              # serve on CPU
```

## Docs
- `docs/DATA_GUIDE.md` — annotation rules and workflow
- `docs/EXPORT.md` — how to convert to GGUF for CPU deployment
- `docs/RLHF_GUIDE.md` — DPO preference fine-tuning
- `scripts/SPECS.md` — full specification for every script

## Schema version
Current: `schemas/training_example_v1.json` v1.0.0
EOF
log "README.md"

# =============================================================================
# 9. SUMMARY
# =============================================================================
header "Done"
echo ""
echo -e "${BOLD}Workspace created at:${RESET} $ROOT"
echo ""
echo -e "${BOLD}Directory tree:${RESET}"
find "$ROOT" -not -path "*/.git/*" | sort | sed "s|$ROOT/||" | awk '
{
  n = split($0, a, "/")
  indent = ""
  for (i = 1; i < n; i++) indent = indent "  "
  print indent (n > 1 ? "├── " : "") a[n]
}'
echo ""
echo -e "${BOLD}Next steps (in order):${RESET}"
echo -e "  1. ${CYAN}cat docs/DATA_GUIDE.md${RESET}          — read annotation rules first"
echo -e "  2. ${CYAN}cat scripts/SPECS.md${RESET}            — read all script specs"
echo -e "  3. Write 25 seed articles → ${CYAN}data/seed/{register}/${RESET}"
echo -e "  4. Implement ${CYAN}scripts/validate_schema.py${RESET} per spec (implement this first)"
echo -e "  5. Implement ${CYAN}scripts/generate_synthetic.py${RESET} and generate raw data"
echo -e "  6. Human review → move to ${CYAN}data/gold/${RESET}"
echo -e "  7. Implement ${CYAN}scripts/augment.py${RESET} and expand dataset"
echo -e "  8. ${CYAN}scripts/split_dataset.py${RESET} → train"
echo ""
