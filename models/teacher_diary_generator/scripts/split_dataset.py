import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path
import logging

def parse_args():
    parser = argparse.ArgumentParser(description="Split dataset into train/val/test.")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--gold-dir", default=str(repo_root / "data" / "gold"), help="Path to gold data directory")
    parser.add_argument("--augmented-dir", default=str(repo_root / "data" / "augmented"), help="Path to augmented data directory")
    parser.add_argument("--output-dir", default=str(repo_root / "data" / "splits"), help="Where to write splits")
    parser.add_argument("--train", type=float, default=0.80)
    parser.add_argument("--val", type=float, default=0.10)
    parser.add_argument("--test", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gold-only-test", action="store_true")
    return parser.parse_args()

def get_dominant_severity(ex):
    severity_order = {"critical": 4, "major": 3, "minor": 2, "none": 1}
    max_sev = "none"
    max_val = 1
    for task_name, task in ex.get("output", {}).items():
        if isinstance(task, dict) and "issues" in task:
            for issue in task["issues"]:
                sev = issue.get("severity", "none")
                val = severity_order.get(sev, 0)
                if val > max_val:
                    max_val = val
                    max_sev = sev
    return max_sev

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    random.seed(args.seed)

    if abs((args.train + args.val + args.test) - 1.0) > 1e-6:
        logging.error("Train, val, and test fractions must sum to 1.0")
        return

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_examples = []
    
    # Load gold
    gold_dir = Path(args.gold_dir)
    if gold_dir.exists():
        for filepath in gold_dir.rglob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_source"] = "gold"
                    all_examples.append(data)
            except Exception as e:
                logging.warning(f"Failed to load {filepath}: {e}")

    # Load augmented
    aug_dir = Path(args.augmented_dir)
    if aug_dir.exists():
        for filepath in aug_dir.rglob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_source"] = "augmented"
                    all_examples.append(data)
            except Exception as e:
                logging.warning(f"Failed to load {filepath}: {e}")

    # Import validate_schema to skip invalid examples
    import sys
    sys.path.append(str(Path(__file__).parent))
    from validate_schema import validate_example, load_schema
    schema_path = repo_root / "schemas" / "training_example_v1.json"
    if schema_path.exists():
        schema_obj = load_schema(schema_path)
        valid_examples = []
        for ex in all_examples:
            if not validate_example(ex, schema_obj):
                valid_examples.append(ex)
            else:
                logging.warning(f"Skipping invalid example {ex.get('id')}")
        all_examples = valid_examples

    if not all_examples:
        logging.error("No valid examples found.")
        return

    # Build stratification groups
    groups = defaultdict(list)
    for ex in all_examples:
        reg = ex.get("metadata", {}).get("register", "unknown")
        sev = get_dominant_severity(ex)
        groups[(reg, sev)].append(ex)

    train_split, val_split, test_split = [], [], []
    report = {"train": defaultdict(int), "val": defaultdict(int), "test": defaultdict(int)}

    for (reg, sev), group in groups.items():
        random.shuffle(group)
        n = len(group)
        n_train = int(n * args.train)
        n_val = int(n * args.val)
        
        train_group = group[:n_train]
        val_group = group[n_train:n_train+n_val]
        test_group = group[n_train+n_val:]

        if args.gold_only_test:
            # Move synthetic from test_group to train_group
            new_test = []
            for ex in test_group:
                if ex["_source"] != "gold":
                    train_group.append(ex)
                else:
                    new_test.append(ex)
            test_group = new_test

        train_split.extend(train_group)
        val_split.extend(val_group)
        test_split.extend(test_group)

        report["train"][f"{reg}_{sev}"] += len(train_group)
        report["val"][f"{reg}_{sev}"] += len(val_group)
        report["test"][f"{reg}_{sev}"] += len(test_group)

    random.shuffle(train_split)
    random.shuffle(val_split)
    random.shuffle(test_split)

    def write_jsonl(filepath, dataset):
        with open(filepath, "w", encoding="utf-8") as f:
            for ex in dataset:
                ex_copy = dict(ex)
                if "_source" in ex_copy:
                    del ex_copy["_source"]
                f.write(json.dumps(ex_copy, ensure_ascii=False) + "\n")

    write_jsonl(out_dir / "train.jsonl", train_split)
    write_jsonl(out_dir / "val.jsonl", val_split)
    write_jsonl(out_dir / "test.jsonl", test_split)

    with open(out_dir / "split_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logging.info(f"Splits saved to {out_dir}")
    logging.info(f"Train: {len(train_split)}, Val: {len(val_split)}, Test: {len(test_split)}")

if __name__ == "__main__":
    main()
