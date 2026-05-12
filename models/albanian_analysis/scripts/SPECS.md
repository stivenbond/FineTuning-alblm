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
