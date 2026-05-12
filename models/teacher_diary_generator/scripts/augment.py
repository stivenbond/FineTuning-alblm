import argparse
import json
import os
import random
import copy
import string
import re
from pathlib import Path
import logging

def parse_args():
    parser = argparse.ArgumentParser(description="Augment training data.")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--gold-dir", default=str(repo_root / "data" / "gold"), help="Path to gold data directory")
    parser.add_argument("--output-dir", default=str(repo_root / "data" / "augmented"), help="Output directory")
    parser.add_argument("--strategy", default="all", help="Comma-separated list of strategies")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--teacher-api-key", help="API key for guidance paraphrase")
    return parser.parse_args()

def get_next_id(output_dir, strategy):
    counter_file = Path(output_dir) / f"id_counter_{strategy}.txt"
    current_id = 1
    if counter_file.exists():
        with open(counter_file, "r") as f:
            content = f.read().strip()
            if content:
                current_id = int(content) + 1
    with open(counter_file, "w") as f:
        f.write(str(current_id))
    return f"alb-aug-{current_id:04d}"

def error_injection(ex):
    # Take a pass/no-issues example and inject one error
    new_ex = copy.deepcopy(ex)
    
    # Check if we can inject
    text = new_ex.get("input", {}).get("article_text", "")
    if not text:
        return None
    
    # Try removing punctuation
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) > 1:
        idx = random.randint(0, len(sentences)-1)
        sentences[idx] = sentences[idx].rstrip(string.punctuation)
        new_text = " ".join(sentences)
        new_ex["input"]["article_text"] = new_text
        
        # Add issue
        task = new_ex["output"].get("grammar", {})
        task["verdict"] = "partial" if task.get("verdict") == "pass" else task.get("verdict", "partial")
        if "issues" not in task:
            task["issues"] = []
        task["issues"].append({
            "location": f"fjalia {idx+1}",
            "issue_type": "Mungesë pikësimi",
            "guidance": "Kontrollo fundin e fjalisë për shenja pikësimi.",
            "severity": "minor"
        })
        new_ex["output"]["grammar"] = task
        return new_ex
    return None

def register_swap(ex, all_guidelines):
    # Swap brand guidelines
    new_ex = copy.deepcopy(ex)
    current_reg = new_ex.get("metadata", {}).get("register")
    if not current_reg or not all_guidelines:
        return None
        
    other_regs = [r for r in all_guidelines.keys() if r != current_reg]
    if not other_regs:
        return None
        
    new_reg = random.choice(other_regs)
    new_ex["input"]["brand_guidelines"] = all_guidelines[new_reg]
    new_ex["metadata"]["register"] = new_reg
    if "writing_style" in new_ex["output"]:
        new_ex["output"]["writing_style"]["expected_register"] = new_reg
        # This will simulate that the text is written in the old register but expected in the new one
        new_ex["output"]["writing_style"]["detected_register"] = current_reg
        new_ex["output"]["writing_style"]["verdict"] = "fail"
        if "issues" not in new_ex["output"]["writing_style"]:
            new_ex["output"]["writing_style"]["issues"] = []
        new_ex["output"]["writing_style"]["issues"].append({
            "location": "gjithë teksti",
            "issue_type": "Regjistër i gabuar",
            "guidance": f"Teksti duket të jetë {current_reg}, por kërkohet të jetë {new_reg}.",
            "severity": "major"
        })
        
    return new_ex

def key_points_removal(ex):
    # Take a structure:pass example
    if ex.get("output", {}).get("structure", {}).get("verdict") != "pass":
        return None
        
    new_ex = copy.deepcopy(ex)
    new_ex["input"]["key_points"] = []
    if "structure" in new_ex["output"]:
        new_ex["output"]["structure"]["verdict"] = "no_brief_provided"
        new_ex["output"]["structure"]["key_points_coverage"] = []
    
    return new_ex

def severity_rebalance(ex):
    new_ex = copy.deepcopy(ex)
    upgraded = False
    for task_name, task in new_ex.get("output", {}).items():
        if isinstance(task, dict) and "issues" in task:
            for issue in task["issues"]:
                if issue.get("severity") == "minor":
                    issue["severity"] = "major"
                    upgraded = True
                    if task.get("verdict") == "pass":
                        task["verdict"] = "partial"
                    break
        if upgraded:
            break
    
    if upgraded:
        return new_ex
    return None

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    random.seed(args.seed)

    gold_dir = Path(args.gold_dir)
    if not gold_dir.exists():
        logging.error("Gold dir does not exist.")
        return

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load all gold examples and collect guidelines
    gold_examples = []
    all_guidelines = {}
    for filepath in gold_dir.rglob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                gold_examples.append(data)
                reg = data.get("metadata", {}).get("register")
                bg = data.get("input", {}).get("brand_guidelines")
                if reg and bg and reg not in all_guidelines:
                    all_guidelines[reg] = bg
        except Exception as e:
            logging.warning(f"Failed to load {filepath}: {e}")

    strategies = ["error_injection", "register_swap", "key_points_removal", "severity_rebalance"]
    if args.strategy != "all":
        strategies = [s.strip() for s in args.strategy.split(",")]

    # Import validate_schema to validate augmented examples
    import sys
    sys.path.append(str(Path(__file__).parent))
    from validate_schema import validate_example, load_schema
    schema_obj = load_schema(repo_root / "schemas" / "training_example_v1.json")

    augmented_count = 0
    for ex in gold_examples:
        for strategy in strategies:
            new_ex = None
            if strategy == "error_injection":
                new_ex = error_injection(ex)
            elif strategy == "register_swap":
                new_ex = register_swap(ex, all_guidelines)
            elif strategy == "key_points_removal":
                new_ex = key_points_removal(ex)
            elif strategy == "severity_rebalance":
                new_ex = severity_rebalance(ex)

            if new_ex:
                new_ex["id"] = get_next_id(out_dir, strategy)
                new_ex["metadata"]["annotator"] = "synthetic"
                new_ex["metadata"]["register"] = "aug"
                
                errors = validate_example(new_ex, schema_obj)
                if not errors:
                    out_file = out_dir / f"{new_ex['id']}.json"
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(new_ex, f, indent=2, ensure_ascii=False)
                    augmented_count += 1
                else:
                    logging.warning(f"Augmented example failed validation: {errors}")

    logging.info(f"Augmentation complete. Generated {augmented_count} examples.")

if __name__ == "__main__":
    main()
