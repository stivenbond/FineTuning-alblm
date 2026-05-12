import argparse
import json
import numpy as np
from scipy.stats import pearsonr, entropy
from sklearn.metrics import accuracy_score, mean_absolute_error
from pathlib import Path
from datetime import datetime
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate model outputs on the test set.")
    parser.add_argument("--predictions", required=True, help="Path to JSONL file of model predictions")
    parser.add_argument("--ground-truth", required=True, help="Path to JSONL file of ground truth")
    parser.add_argument("--output", help="Path to write metrics JSON")
    return parser.parse_args()

def safe_mae(y_true, y_pred):
    if not y_true: return 0.0
    return mean_absolute_error(y_true, y_pred)

def safe_accuracy(y_true, y_pred):
    if not y_true: return 0.0
    return accuracy_score(y_true, y_pred)

def safe_pearsonr(y_true, y_pred):
    if len(y_true) < 2: return 0.0
    # Add small noise if variance is zero
    if np.var(y_true) == 0 or np.var(y_pred) == 0:
        return 0.0
    r, _ = pearsonr(y_true, y_pred)
    return float(r) if not np.isnan(r) else 0.0

def calculate_severity_kl(true_issues, pred_issues):
    def get_dist(issues):
        counts = {"critical": 0, "major": 0, "minor": 0}
        for i in issues:
            counts[i.get("severity", "minor")] += 1
        total = sum(counts.values())
        if total == 0: return np.array([1/3, 1/3, 1/3])
        return np.array([counts["critical"]/total, counts["major"]/total, counts["minor"]/total])

    if not true_issues and not pred_issues:
        return 0.0
    p = get_dist(true_issues)
    q = get_dist(pred_issues)
    # add smoothing to avoid inf
    p = p + 1e-10
    q = q + 1e-10
    p = p / np.sum(p)
    q = q / np.sum(q)
    return float(entropy(p, q))

def main():
    args = parse_args()
    
    gt_dict = {}
    with open(args.ground_truth, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            gt_dict[data["id"]] = data
            
    preds = []
    with open(args.predictions, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                preds.append(json.loads(line))
            except json.JSONDecodeError:
                pass # invalid json

    total_gt = len(gt_dict)
    valid_json = len(preds)
    
    # Check schema compliance (simulate with try except if validator available)
    repo_root = Path(__file__).parent.parent
    sys.path.append(str(repo_root / "scripts"))
    schema_compliant = 0
    try:
        from validate_schema import load_schema, validate_example
        schema_obj = load_schema(repo_root / "schemas" / "training_example_v1.json")
        for p in preds:
            if not validate_example(p, schema_obj):
                schema_compliant += 1
    except:
        schema_compliant = valid_json # fallback

    metrics = {
        "global": {
            "total_examples": total_gt,
            "json_validity_rate": valid_json / total_gt if total_gt else 0,
            "schema_compliance_rate": schema_compliant / total_gt if total_gt else 0,
            "full_pass_rate": 0
        },
        "tasks": {}
    }

    # Guidance tasks
    for task in ["grammar", "writing_style", "formatting"]:
        t_verdict, p_verdict = [], []
        t_issue_cnt, p_issue_cnt = [], []
        kl_divs = []
        
        for p in preds:
            if p.get("id") not in gt_dict: continue
            gt = gt_dict[p["id"]].get("output", {}).get(task, {})
            pr = p.get("output", {}).get(task, {})
            
            t_verdict.append(gt.get("verdict", "pass"))
            p_verdict.append(pr.get("verdict", "pass"))
            
            t_issues = gt.get("issues", [])
            p_issues = pr.get("issues", [])
            t_issue_cnt.append(len(t_issues))
            p_issue_cnt.append(len(p_issues))
            
            kl_divs.append(calculate_severity_kl(t_issues, p_issues))
            
        metrics["tasks"][task] = {
            "verdict_accuracy": safe_accuracy(t_verdict, p_verdict),
            "issue_count_mae": safe_mae(t_issue_cnt, p_issue_cnt),
            "severity_kl_divergence": float(np.mean(kl_divs)) if kl_divs else 0.0
        }

    # Scored tasks
    for task in ["brand_compliance", "marketing_compliance"]:
        t_verdict, p_verdict = [], []
        t_score, p_score = [], []
        
        for p in preds:
            if p.get("id") not in gt_dict: continue
            gt = gt_dict[p["id"]].get("output", {}).get(task, {})
            pr = p.get("output", {}).get(task, {})
            
            t_verdict.append(gt.get("verdict", "pass"))
            p_verdict.append(pr.get("verdict", "pass"))
            t_score.append(gt.get("score", 100))
            p_score.append(pr.get("score", 100))
            
        metrics["tasks"][task] = {
            "verdict_accuracy": safe_accuracy(t_verdict, p_verdict),
            "score_mae": safe_mae(t_score, p_score),
            "score_pearson": safe_pearsonr(t_score, p_score)
        }

    # Structure task
    t_verdict, p_verdict = [], []
    t_type, p_type = [], []
    t_coverage, p_coverage = [], [] # flattened
    
    full_passes = 0
    for p in preds:
        if p.get("id") not in gt_dict: continue
        g_out = gt_dict[p["id"]].get("output", {})
        p_out = p.get("output", {})
        
        # global full pass check
        all_match = True
        for tk in ["grammar", "writing_style", "formatting", "brand_compliance", "marketing_compliance", "structure"]:
            if g_out.get(tk, {}).get("verdict") != p_out.get(tk, {}).get("verdict"):
                all_match = False
                break
        if all_match:
            full_passes += 1

        gt = g_out.get("structure", {})
        pr = p_out.get("structure", {})
        
        t_verdict.append(gt.get("verdict", "pass"))
        p_verdict.append(pr.get("verdict", "pass"))
        t_type.append(gt.get("structure_type_detected", "unclear"))
        p_type.append(pr.get("structure_type_detected", "unclear"))
        
        gt_kp = {kp.get("key_point"): kp.get("covered") for kp in gt.get("key_points_coverage", [])}
        pr_kp = {kp.get("key_point"): kp.get("covered") for kp in pr.get("key_points_coverage", [])}
        
        for kp, cov in gt_kp.items():
            t_coverage.append(1 if cov else 0)
            p_coverage.append(1 if pr_kp.get(kp) else 0)

    metrics["global"]["full_pass_rate"] = full_passes / total_gt if total_gt else 0

    if t_coverage:
        # recall
        true_pos = sum(1 for t, p in zip(t_coverage, p_coverage) if t == 1 and p == 1)
        actual_pos = sum(t_coverage)
        recall = true_pos / actual_pos if actual_pos else 0
        
        # precision
        pred_pos = sum(p_coverage)
        precision = true_pos / pred_pos if pred_pos else 0
    else:
        recall, precision = 0, 0

    metrics["tasks"]["structure"] = {
        "verdict_accuracy": safe_accuracy(t_verdict, p_verdict),
        "structure_type_accuracy": safe_accuracy(t_type, p_type),
        "key_point_coverage_recall": recall,
        "key_point_coverage_precision": precision
    }

    out_path = args.output
    if not out_path:
        out_dir = repo_root / "evals" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{ts}.json"
        
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        
    print(f"Metrics saved to {out_path}")
    print(json.dumps(metrics["global"], indent=2))

if __name__ == "__main__":
    main()
