import logging
from datetime import datetime

def validate_and_repair(raw: dict, **kwargs) -> tuple[dict, list[str]]:
    """
    Validates and repairs the output of the Teacher Diary Generator.
    Expected structure:
    {
        "metadata": { "version": "1.0.0", "generated_at": "..." },
        "entry": { "field1": "...", "field2": "..." },
        "tool_calls": [ ... ]
    }
    """
    repairs = []
    
    # 1. Ensure metadata
    if "metadata" not in raw:
        raw["metadata"] = {
            "version": "1.0.0",
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
        repairs.append("Missing metadata injected.")
    else:
        if "version" not in raw["metadata"]:
            raw["metadata"]["version"] = "1.0.0"
        if "generated_at" not in raw["metadata"]:
            raw["metadata"]["generated_at"] = datetime.utcnow().isoformat() + "Z"

    # 2. Ensure entry
    if "entry" not in raw:
        raw["entry"] = {}
        repairs.append("Missing entry dict injected.")
    
    if not isinstance(raw["entry"], dict):
        raw["entry"] = { "raw_content": str(raw["entry"]) }
        repairs.append("Entry was not a dict, converted to raw_content.")

    # 3. Tool calls validation
    if "tool_calls" in raw:
        if not isinstance(raw["tool_calls"], list):
            raw["tool_calls"] = []
            repairs.append("Invalid tool_calls format, reset to empty list.")
        else:
            for i, tc in enumerate(raw["tool_calls"]):
                if not isinstance(tc, dict) or "tool" not in tc or "parameters" not in tc:
                    raw["tool_calls"].pop(i)
                    repairs.append(f"Removed malformed tool call at index {i}.")

    # 4. Optional: Cross-check with requested fields if passed in kwargs
    requested_fields = kwargs.get("target_fields")
    if requested_fields and isinstance(requested_fields, list):
        for field in requested_fields:
            if field not in raw["entry"]:
                raw["entry"][field] = "Nuk u gjenerua informacion për këtë fushë."
                repairs.append(f"Missing requested field '{field}' injected with placeholder.")

    return raw, repairs
