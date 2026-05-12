import json
import re
import argparse
from pathlib import Path

def build_prompt(
    article_text: str,
    brand_guidelines: str = "",
    key_points: list = None,
    register_hint: str = "",
    **kwargs
) -> str:
    if key_points is None:
        key_points = []
        
    brand_guidelines_section = ""
    if brand_guidelines:
        brand_guidelines_section = f"## Udhëzimet e Markës\n{brand_guidelines}"

    key_points_section = ""
    if key_points:
        kp_list = "\n".join([f"{i+1}. {kp}" for i, kp in enumerate(key_points)])
        key_points_section = f"## Pikat Kryesore të Briefit\n{kp_list}"
    else:
        key_points_section = "## Pikat Kryesore\nAsnjë brief nuk është dhënë."

    prompt = f"""<start_of_turn>system
Je një redaktor ekspert i gjuhës shqipe. Analizon artikujt dhe prodhon vlerësime të strukturuara JSON.
Rregull kritik: fushat "guidance" duhet të jenë vetëm udhëzuese — kurrë mos rishkruaj tekstin.
Së pari arsyeto brenda blloqeve <think>...</think> dhe më pas kthe objektin përfundimtar JSON.
{brand_guidelines_section}
<end_of_turn>
<start_of_turn>user
{key_points_section}

## Artikulli për Analizë
{article_text}

Prodhoni analizën e plotë JSON për të 6 detyrat.
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", required=True, help="Path to example JSON")
    args = parser.parse_args()

    example_path = Path(args.example)
    if not example_path.exists():
        print("Example file not found.")
        return

    with open(example_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    inp = data.get("input", {})
    prompt = build_prompt(
        article_text=inp.get("article_text", ""),
        brand_guidelines=inp.get("brand_guidelines", ""),
        key_points=inp.get("key_points", []),
        register_hint=data.get("metadata", {}).get("register", "")
    )
    print(prompt)

if __name__ == "__main__":
    main()
