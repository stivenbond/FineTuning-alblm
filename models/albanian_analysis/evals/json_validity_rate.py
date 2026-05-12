import argparse
import json
import sys
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="Standalone fast check of raw model output files.")
    parser.add_argument("--predictions", required=True, help="Path to JSONL of raw model outputs")
    parser.add_argument("--strict", action="store_true", help="Also run validate_schema, not just json.loads")
    parser.add_argument("--threshold", type=float, default=0.90, help="Fail if validity rate is below threshold")
    return parser.parse_args()

def main():
    args = parse_args()
    pred_path = Path(args.predictions)
    
    if not pred_path.exists():
        print(f"Error: Predictions file not found at {pred_path}")
        sys.exit(1)

    schema_obj = None
    if args.strict:
        # Try to import validate_schema
        repo_root = Path(__file__).parent.parent
        sys.path.append(str(repo_root / "scripts"))
        try:
            from validate_schema import load_schema, validate_example
            schema_path = repo_root / "schemas" / "training_example_v1.json"
            schema_obj = load_schema(schema_path)
        except Exception as e:
            print(f"Error loading schema validator: {e}")
            sys.exit(1)

    total = 0
    valid = 0
    failures = []

    with open(pred_path, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                failures.append((line_idx, f"JSON parse error: {e}"))
                continue
            
            if args.strict and schema_obj:
                errors = validate_example(data, schema_obj)
                if errors:
                    failures.append((line_idx, f"Schema validation errors: {errors}"))
                    continue
            
            valid += 1

    if total == 0:
        print("No predictions found in file.")
        sys.exit(0)

    validity_rate = valid / total
    print(f"Total: {total}")
    print(f"Valid: {valid}")
    print(f"Validity Rate: {validity_rate:.2%}")

    if failures:
        print("\nFirst 10 Failures:")
        for line_idx, msg in failures[:10]:
            print(f"Line {line_idx}: {msg}")

    if validity_rate < args.threshold:
        print(f"\nError: Validity rate {validity_rate:.2%} is below threshold {args.threshold:.2%}")
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
