import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.append(str(repo_root / "scripts"))
from build_prompt import parse_response

def test_parse_response_with_think_block():
    response_text = """<think>
Ky është një proces arsyetimi. Unë po shikoj tekstin.
</think>
{
  "grammar": {
    "verdict": "pass",
    "issues": []
  }
}
"""
    result = parse_response(response_text)
    assert not result.get("parse_error")
    assert "grammar" in result
    assert result["grammar"]["verdict"] == "pass"

def test_parse_response_without_think_block():
    response_text = """{
  "grammar": {
    "verdict": "fail",
    "issues": []
  }
}"""
    result = parse_response(response_text)
    assert not result.get("parse_error")
    assert result["grammar"]["verdict"] == "fail"

def test_parse_response_malformed():
    response_text = """<think>Arsyetim...</think>
{
  "grammar": {
    "verdict": "pass"
  },
}
"""
    result = parse_response(response_text)
    assert not result.get("parse_error")
    assert result["grammar"]["verdict"] == "pass"
