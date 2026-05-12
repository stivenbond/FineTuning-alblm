import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.append(str(repo_root / "scripts"))
from output_validator import validate_and_repair, fuzzy_match_verdict

def test_fuzzy_match_verdict():
    assert fuzzy_match_verdict("pass") == "pass"
    assert fuzzy_match_verdict("passed") == "pass"
    assert fuzzy_match_verdict("FAIL") == "fail"
    assert fuzzy_match_verdict("failed") == "fail"
    assert fuzzy_match_verdict("partiall") == "partial"
    assert fuzzy_match_verdict("random_string") == "fail"

def test_validate_and_repair_missing_tasks():
    raw = {}
    repaired, modifications = validate_and_repair(raw)
    
    assert "grammar" in repaired
    assert repaired["grammar"]["verdict"] == "fail"
    assert "formatting" in repaired
    assert repaired["brand_compliance"]["score"] == 0
    assert len(modifications) > 0
    assert repaired.get("low_confidence") is True

def test_validate_and_repair_clamp_scores():
    raw = {
        "grammar": {"verdict": "pass", "issues": []},
        "writing_style": {"verdict": "pass", "issues": [], "detected_register": "editorial", "expected_register": "editorial"},
        "formatting": {"verdict": "pass", "issues": []},
        "brand_compliance": {"verdict": "pass", "score": 150, "issues": []},
        "marketing_compliance": {"verdict": "pass", "score": -10, "issues": []},
        "structure": {"verdict": "pass", "key_points_coverage": [], "structure_type_detected": "standard"}
    }
    
    repaired, modifications = validate_and_repair(raw)
    assert repaired["brand_compliance"]["score"] == 100
    assert repaired["marketing_compliance"]["score"] == 0
    assert len(modifications) == 2
    assert not repaired.get("low_confidence")

def test_validate_and_repair_structure_verdict():
    raw = {
        "grammar": {"verdict": "pass", "issues": []},
        "writing_style": {"verdict": "pass", "issues": [], "detected_register": "editorial", "expected_register": "editorial"},
        "formatting": {"verdict": "pass", "issues": []},
        "brand_compliance": {"verdict": "pass", "score": 100, "issues": []},
        "marketing_compliance": {"verdict": "pass", "score": 100, "issues": []},
        "structure": {"verdict": "pass", "key_points_coverage": [], "structure_type_detected": "standard"}
    }
    
    # Simulating empty key_points in input
    repaired, modifications = validate_and_repair(raw, key_points=[])
    assert repaired["structure"]["verdict"] == "no_brief_provided"
