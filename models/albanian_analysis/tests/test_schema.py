import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.append(str(repo_root / "scripts"))
from validate_schema import validate_example, load_schema

schema_obj = load_schema(repo_root / "schemas" / "training_example_v1.json")

def test_valid_example():
    valid_ex = {
        "id": "alb-editorial-1234",
        "metadata": {
            "register": "editorial",
            "annotator": "human",
            "rlhf_eligible": True,
            "version": "1.0.0",
            "reviewer": "test",
            "reviewed_at": "2023-01-01"
        },
        "input": {
            "brand_guidelines": "",
            "key_points": [],
            "article_text": "Kjo është një fjali hyrëse mjaft e gjatë për të arritur limitin prej njëqind karakteresh, megjithëse ndoshta do të duhet të shkruaj edhe pak më shumë për të qenë i sigurt që e kalon pragun."
        },
        "output": {
            "grammar": {"verdict": "pass", "issues": []},
            "writing_style": {"verdict": "pass", "detected_register": "editorial", "expected_register": "editorial", "issues": []},
            "formatting": {"verdict": "pass", "issues": []},
            "brand_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "marketing_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "structure": {"verdict": "no_brief_provided", "key_points_coverage": [], "structure_type_detected": "standard"}
        }
    }
    errors = validate_example(valid_ex, schema_obj)
    assert not errors, f"Expected valid, got errors: {errors}"

def test_invalid_example_id():
    invalid_ex = {
        "id": "bad-id-123",  # Invalid ID pattern
        "metadata": {"register": "editorial", "annotator": "human", "rlhf_eligible": True, "version": "1.0.0", "reviewer": "test", "reviewed_at": "2023-01-01"},
        "input": {"brand_guidelines": "", "key_points": [], "article_text": "x" * 150},
        "output": {
            "grammar": {"verdict": "pass", "issues": []},
            "writing_style": {"verdict": "pass", "detected_register": "editorial", "expected_register": "editorial", "issues": []},
            "formatting": {"verdict": "pass", "issues": []},
            "brand_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "marketing_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "structure": {"verdict": "no_brief_provided", "key_points_coverage": [], "structure_type_detected": "standard"}
        }
    }
    errors = validate_example(invalid_ex, schema_obj)
    assert errors
    assert any("ID must match" in e for e in errors)

def test_invalid_quotes_in_guidance():
    invalid_ex = {
        "id": "alb-editorial-1234",
        "metadata": {"register": "editorial", "annotator": "human", "rlhf_eligible": True, "version": "1.0.0", "reviewer": "test", "reviewed_at": "2023-01-01"},
        "input": {"brand_guidelines": "", "key_points": [], "article_text": "x" * 150},
        "output": {
            "grammar": {
                "verdict": "partial", 
                "issues": [{"location": "këtu", "issue_type": "gabim", "guidance": 'Ndreqe kështu: "teksti i ri"', "severity": "minor"}]
            },
            "writing_style": {"verdict": "pass", "detected_register": "editorial", "expected_register": "editorial", "issues": []},
            "formatting": {"verdict": "pass", "issues": []},
            "brand_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "marketing_compliance": {"verdict": "pass", "score": 100, "issues": []},
            "structure": {"verdict": "no_brief_provided", "key_points_coverage": [], "structure_type_detected": "standard"}
        }
    }
    errors = validate_example(invalid_ex, schema_obj)
    assert errors
    assert any("contains quotes" in e for e in errors)
