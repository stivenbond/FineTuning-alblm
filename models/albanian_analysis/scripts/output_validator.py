import difflib
import logging

class OutputValidationError(Exception):
    pass

def fuzzy_match_verdict(raw_verdict: str) -> str:
    allowed = ["pass", "fail", "partial", "no_brief_provided"]
    if not isinstance(raw_verdict, str):
        return "fail"
    raw_lower = raw_verdict.lower().strip()
    if raw_lower in allowed:
        return raw_lower
    
    matches = difflib.get_close_matches(raw_lower, allowed, n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return "fail"

def validate_and_repair(raw: dict, **kwargs) -> tuple[dict, list[str]]:
    repairs = []
    
    # Check if key_points were provided in the request
    key_points = kwargs.get("key_points", [])
    key_points_empty = not key_points
    
    # 1. Missing task key -> empty scaffold
    tasks = {
        "grammar": {"verdict": "fail", "issues": []},
        "writing_style": {"verdict": "fail", "issues": [], "detected_register": "unspecified", "expected_register": "unspecified"},
        "formatting": {"verdict": "fail", "issues": []},
        "brand_compliance": {"verdict": "fail", "score": 0, "issues": []},
        "marketing_compliance": {"verdict": "fail", "score": 0, "issues": []},
        "structure": {"verdict": "fail", "key_points_coverage": [], "structure_type_detected": "unclear", "guidance": "Shih seksionin përkatës për detaje."}
    }
    
    for tk, scaffold in tasks.items():
        if tk not in raw:
            raw[tk] = scaffold
            repairs.append(f"Missing task {tk} injected scaffold.")
        else:
            task = raw[tk]
            # Ensure required fields
            for k, v in scaffold.items():
                if k not in task:
                    task[k] = v
                    repairs.append(f"Task {tk} missing key {k}, injected default.")
    
    # Check all tasks
    for tk, task in raw.items():
        if tk not in tasks: continue
        
        # 2. Score out of range
        if "score" in task:
            try:
                score = float(task["score"])
                if score < 0:
                    task["score"] = 0
                    repairs.append(f"Task {tk} clamped score from {score} to 0")
                elif score > 100:
                    task["score"] = 100
                    repairs.append(f"Task {tk} clamped score from {score} to 100")
            except (ValueError, TypeError):
                task["score"] = 0
                repairs.append(f"Task {tk} invalid score reset to 0")

        # 3. Invalid verdict string
        original_verdict = task.get("verdict", "")
        new_verdict = fuzzy_match_verdict(original_verdict)
        if original_verdict != new_verdict:
            task["verdict"] = new_verdict
            repairs.append(f"Task {tk} matched verdict {original_verdict} to {new_verdict}")

        # 4 & 5. Issue missing severity/guidance
        if "issues" in task and isinstance(task["issues"], list):
            for i, issue in enumerate(task["issues"]):
                if not isinstance(issue, dict): continue
                if "severity" not in issue or issue["severity"] not in ["critical", "major", "minor"]:
                    issue["severity"] = "minor"
                    repairs.append(f"Task {tk} issue {i} severity reset to minor")
                if "guidance" not in issue or not issue["guidance"].strip():
                    issue["guidance"] = "Shih seksionin përkatës për detaje."
                    repairs.append(f"Task {tk} issue {i} guidance injected")

    # 6. structure.verdict
    if key_points_empty:
        if raw["structure"]["verdict"] != "no_brief_provided":
            raw["structure"]["verdict"] = "no_brief_provided"
            repairs.append("Structure verdict forced to no_brief_provided due to empty key_points")

    # 7. Low confidence flag
    if len(repairs) > 3:
        raw["low_confidence"] = True

    return raw, repairs
