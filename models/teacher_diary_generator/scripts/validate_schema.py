import json
import argparse
import re
import sys
from pathlib import Path
import jsonschema

def parse_args():
    parser = argparse.ArgumentParser(description="Validate teacher diary training examples against schema.")
    parser.add_argument("--input", required=True, help="Path to a .json file, .jsonl file, or directory")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--schema", default=str(repo_root / "schemas" / "diary_entry_v1.json"), help="Path to schema JSON")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix common issues using the output_validator")
    return parser.parse_args()

def load_schema(schema_path):
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_example(ex, schema_obj):
    errors = []
    try:
        jsonschema.validate(instance=ex, schema=schema_obj)
    except jsonschema.exceptions.ValidationError as e:
        errors.append(f"Schema violation: {e.message}")
    
    # Custom rule: ID pattern
    if "id" in ex and not re.match(r'^td-[0-9]{4}$', ex["id"]):
        errors.append("ID must match td-[0-9]{4}")
        
    return errors

def main():
    args = parse_args()
    
    # Import validator for fixing
    validator_mod = None
    if args.fix:
        import importlib.util
        scripts_dir = Path(__file__).parent
        val_path = scripts_dir / "output_validator.py"
        if val_path.exists():
            spec = importlib.util.spec_from_file_location("output_validator", val_path)
            validator_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator_mod)

    schema_obj = load_schema(args.schema)
    input_path = Path(args.input)
    
    files_to_process = []
    if input_path.is_file():
        files_to_process.append(input_path)
    elif input_path.is_dir():
        files_to_process.extend(input_path.glob("*.json"))
        files_to_process.extend(input_path.glob("*.jsonl"))

    for file_path in files_to_process:
        is_jsonl = file_path.suffix == ".jsonl"
        total, valid, fixed_cnt = 0, 0, 0
        output_lines = []
        needs_write = False

        with open(file_path, "r", encoding="utf-8") as f:
            if is_jsonl:
                lines = f.readlines()
            else:
                lines = [f.read()]

            for line in lines:
                if not line.strip(): continue
                total += 1
                try:
                    ex = json.loads(line)
                    
                    if args.fix and validator_mod:
                        # Output in training data is usually under "output" key
                        # The validator expects the content of the "output"
                        if "output" in ex:
                            repaired, repairs = validator_mod.validate_and_repair(ex["output"])
                            if repairs:
                                ex["output"] = repaired
                                fixed_cnt += 1
                                needs_write = True
                    
                    errors = validate_example(ex, schema_obj)
                    if not errors:
                        valid += 1
                    else:
                        print(f"[{file_path.name}] Invalid example: {errors}")
                    
                    output_lines.append(json.dumps(ex, ensure_ascii=False) + ("\n" if is_jsonl else ""))
                except Exception as e:
                    print(f"[{file_path.name}] Error: {e}")

        if needs_write and args.fix:
            with open(file_path, "w", encoding="utf-8") as f:
                if is_jsonl:
                    f.writelines(output_lines)
                else:
                    f.write(json.dumps(json.loads(output_lines[0]), indent=2, ensure_ascii=False))

        print(f"{file_path.name}: Total {total} | Valid {valid} | Fixed {fixed_cnt}")

if __name__ == "__main__":
    main()
