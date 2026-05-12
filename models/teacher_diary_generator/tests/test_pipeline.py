import pytest
import sys
from pathlib import Path
import json

# Add scripts to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.append(str(scripts_dir))

from output_validator import validate_and_repair
from build_prompt import build_prompt, parse_response

def test_validate_and_repair_missing_metadata():
    raw = {"entry": {"Summary": "Test"}}
    repaired, repairs = validate_and_repair(raw)
    assert "metadata" in repaired
    assert "generated_at" in repaired["metadata"]
    assert any("metadata" in r for r in repairs)

def test_validate_and_repair_missing_field():
    raw = {
        "metadata": {"version": "1.0.0", "generated_at": "2026-04-29"},
        "entry": {"Summary": "Test"}
    }
    repaired, repairs = validate_and_repair(raw, target_fields=["Summary", "Homework"])
    assert "Homework" in repaired["entry"]
    assert "Nuk u gjenerua" in repaired["entry"]["Homework"]
    assert any("Homework" in r for r in repairs)

def test_build_prompt_basic():
    context = {"subject": "Math"}
    fields = ["Summary"]
    prompt = build_prompt(context_data=context, target_fields=fields)
    assert "Math" in prompt
    assert "Summary" in prompt
    assert "<start_of_turn>user" in prompt

def test_parse_response_with_think():
    response = "<think>Reasoning here</think>{\"entry\": {\"Summary\": \"Done\"}}"
    parsed = parse_response(response)
    assert "entry" in parsed
    assert parsed["entry"]["Summary"] == "Done"
    assert "think" not in str(parsed)

def test_parse_response_invalid_json():
    response = "This is not JSON"
    parsed = parse_response(response)
    assert parsed.get("parse_error") is True
