import json
import argparse
import re
import sys
from pathlib import Path
import jsonschema

def parse_args():
    parser = argparse.ArgumentParser(description="Validate training examples against schema.")
    parser.add_argument("--input", required=True, help="Path to a .jsonl file or directory of .jsonl files")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--schema", default=str(repo_root / "schemas" / "training_example_v1.json"), help="Path to schema JSON")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix common issues")
    parser.add_argument("--strict", action="store_true", help="Fail on any warning")
    parser.add_argument("--report", help="Path to write JSON report of failures")
    return parser.parse_args()

def load_schema(schema_path):
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def check_guidance_quotes(text):
    if not text:
        return True
    if re.search(r'[«»""]', text):
        return False
    return True

def fix_example(ex):
    fixed = False
    
    # 1. Missing empty arrays
    for task_name in ["grammar", "writing_style", "formatting", "brand_compliance", "marketing_compliance"]:
        if task_name in ex.get("output", {}):
            task = ex["output"][task_name]
            if "issues" not in task:
                task["issues"] = []
                fixed = True
    
    # 2. Wrong verdict casing
    for task_name, task in ex.get("output", {}).items():
        if "verdict" in task:
            if isinstance(task["verdict"], str):
                lower_v = task["verdict"].lower()
                if task["verdict"] != lower_v:
                    task["verdict"] = lower_v
                    fixed = True
    
    # 3. structure.key_points_coverage missing
    if "structure" in ex.get("output", {}):
        if "key_points_coverage" not in ex["output"]["structure"]:
            ex["output"]["structure"]["key_points_coverage"] = []
            fixed = True

    return ex, fixed

def validate_example(ex, schema_obj):
    errors = []
    
    try:
        jsonschema.validate(instance=ex, schema=schema_obj)
    except jsonschema.exceptions.ValidationError as e:
        errors.append(f"Schema violation: {e.message}")

    # Additional manual rules
    # 3. id pattern
    if "id" in ex and not re.match(r'^alb-[a-z]+-[0-9]{4}$', ex["id"]):
        errors.append("ID must match alb-[a-z]+-[0-9]{4}")
    
    # 9. For structure task: if input.key_points is empty, verdict must be no_brief_provided
    inp = ex.get("input", {})
    key_points = inp.get("key_points", [])
    structure = ex.get("output", {}).get("structure", {})
    if not key_points and structure.get("verdict") != "no_brief_provided":
        errors.append("structure.verdict must be no_brief_provided when key_points is empty")

    # 10. All guidance fields: must not contain quoted text blocks
    def check_issues(issues):
        for issue in issues:
            guidance = issue.get("guidance", "")
            if not guidance:
                errors.append("Empty guidance string found")
            if not check_guidance_quotes(guidance):
                errors.append(f"Guidance field contains quotes: {guidance}")

    for task_name in ["grammar", "writing_style", "formatting", "brand_compliance", "marketing_compliance"]:
        task = ex.get("output", {}).get(task_name, {})
        check_issues(task.get("issues", []))

    # structure task has one guidance field at task level
    str_guidance = structure.get("guidance", "")
    if str_guidance and not check_guidance_quotes(str_guidance):
        errors.append("Structure guidance field contains quotes")

    return errors

def main():
    args = parse_args()
    
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"Error: Schema not found at {schema_path}")
        sys.exit(1)
        
    schema_obj = load_schema(schema_path)

    input_path = Path(args.input)
    files_to_process = []
    if input_path.is_file():
        files_to_process.append(input_path)
    elif input_path.is_dir():
        files_to_process.extend(input_path.glob("*.jsonl"))
    else:
        print(f"Error: Input not found at {input_path}")
        sys.exit(1)

    all_failures = []
    has_invalid = False

    for file_path in files_to_process:
        total, valid, invalid, fixed_cnt = 0, 0, 0, 0
        lines_to_write = []
        needs_write = False

        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                total += 1
                try:
                    ex = json.loads(line)
                except json.JSONDecodeError as e:
                    invalid += 1
                    has_invalid = True
                    all_failures.append({"file": str(file_path), "line": line_idx, "errors": [f"JSON parse error: {e}"]})
                    lines_to_write.append(line)
                    continue

                fixed = False
                if args.fix:
                    ex, fixed = fix_example(ex)
                    if fixed:
                        needs_write = True
                        fixed_cnt += 1

                errors = validate_example(ex, schema_obj)
                
                if errors:
                    invalid += 1
                    has_invalid = True
                    all_failures.append({"file": str(file_path), "line": line_idx, "id": ex.get("id"), "errors": errors})
                else:
                    valid += 1

                lines_to_write.append(json.dumps(ex, ensure_ascii=False) + "\n" if fixed else line)

        if needs_write and args.fix:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines_to_write)

        print(f"{file_path.name}: Total {total} | Valid {valid} | Invalid {invalid} | Fixed {fixed_cnt}")

    if args.report and all_failures:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(all_failures, f, indent=2, ensure_ascii=False)

    if has_invalid:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
