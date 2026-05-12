import json
import re
from pathlib import Path

def build_prompt(
    context_data: dict = None,
    target_fields: list = None,
    language: str = "sq", 
    additional_instructions: str = "",
    **kwargs
) -> str:
    """
    Builds a prompt for the Teacher Diary Generator.
    
    Args:
        context_data: Dictionary containing info from MCP (students, lesson plan, raw notes).
        target_fields: List of field names the user wants in the final JSON.
        language: Target language for generation.
        additional_instructions: Any extra constraints.
    """
    
    if context_data is None:
        context_data = {}
    if target_fields is None:
        target_fields = ["Summary"]
        
    fields_str = "\n".join([f"- {field}" for field in target_fields])
    context_str = json.dumps(context_data, indent=2, ensure_ascii=False)

    system_msg = "Je një asistent inteligjent për mësuesit. Detyra jote është të gjenerosh ditarë mësimorë të strukturuar në JSON."
    if language == "en":
        system_msg = "You are an intelligent assistant for teachers. Your task is to generate structured teacher diaries in JSON."

    prompt = f"""<start_of_turn>system
{system_msg}
Rregullat:
1. Përdor blloqet <think>...</think> për të arsyetuar rreth kontekstit përpara se të krijosh JSON-in.
2. Gjenero JSON-in duke përdorur saktësisht fushat e kërkuara nga përdoruesi.
3. Nëse konteksti sugjeron veprime (si detyra shtëpie ose njoftime), shto një fushë "tool_calls".
{additional_instructions}
<end_of_turn>
<start_of_turn>user
### Konteksti nga MCP:
{context_str}

### Fushat e Kërkuara në Ditar:
{fields_str}

Gjenero ditarin e plotë në formatin JSON.
<end_of_turn>
<start_of_turn>model
"""
    return prompt

def parse_response(response_text: str) -> dict:
    # Remove <think> block if present
    response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
    
    # Try direct parsing
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Extract first {...} block
    match = re.search(r'(\{.*\})', response_text, re.DOTALL)
    if match:
        block = match.group(1)
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            # Try stripping trailing commas
            block_fixed = re.sub(r',(\s*[}\]])', r'\1', block)
            try:
                return json.loads(block_fixed)
            except json.JSONDecodeError:
                pass

    return {"parse_error": True, "raw": response_text}
