import json
import pandas as pd
from pathlib import Path
import argparse
from build_prompt import build_prompt

def load_json_report(file_path):
    """Loads a JSON report, handling potential encoding issues and different key sets."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract input fields with fallback for Albanian keys
    inp = data.get("input", {})
    
    # Article text
    article_text = inp.get("article_text") or inp.get("teksti_i_artikullit") or ""
    
    # Brand guidelines (can be string or dict)
    brand_guidelines_raw = inp.get("brand_guidelines") or inp.get("udhëzimet_e_markës") or ""
    if isinstance(brand_guidelines_raw, dict):
        brand_guidelines = json.dumps(brand_guidelines_raw, ensure_ascii=False, indent=2)
    else:
        brand_guidelines = str(brand_guidelines_raw)
        
    # Key points
    key_points = inp.get("key_points") or inp.get("pikat_kryesore") or []
    
    # Metadata / Register hint
    metadata = data.get("metadata", {})
    register_hint = metadata.get("register") or metadata.get("regjistri") or ""
    
    # Output (Completion)
    output_data = data.get("output", {})
    
    return {
        "article_text": article_text,
        "brand_guidelines": brand_guidelines,
        "key_points": key_points,
        "register_hint": register_hint,
        "output_json": json.dumps(output_data, ensure_ascii=False, indent=2),
        "id": data.get("id", file_path.stem)
    }

def get_unsloth_format(report_data):
    """
    Returns components for Unsloth-compatible instruction fine-tuning.
    Splits the prompt into instruction (system) and input (user content).
    """
    # System part (Instruction)
    instruction = (
        "Je një redaktor ekspert i gjuhës shqipe. Analizon artikujt dhe prodhon vlerësime të strukturuara JSON.\n"
        "Rregull kritik: fushat \"guidance\" duhet të jenë vetëm udhëzuese — kurrë mos rishkruaj tekstin.\n"
        "Së pari arsyeto brenda blloqeve <think>...</think> dhe më pas kthe objektin përfundimtar JSON."
    )
    if report_data["brand_guidelines"]:
        instruction += f"\n\n## Udhëzimet e Markës\n{report_data['brand_guidelines']}"

    # User part (Input)
    kp_list = "\n".join([f"{i+1}. {kp}" for i, kp in enumerate(report_data['key_points'])]) if report_data['key_points'] else "Asnjë brief nuk është dhënë."
    user_input = (
        f"## Pikat Kryesore të Briefit\n{kp_list}\n\n"
        f"## Artikulli për Analizë\n{report_data['article_text']}\n\n"
        "Prodhoni analizën e plotë JSON për të 6 detyrat."
    )

    # Model part (Output)
    # We add a placeholder <think> block because the system prompt requires it
    # Training without it would teach the model to ignore its own 'think' instruction.
    thinking_placeholder = "<think>\nAnalizimi i artikullit për gramatikën, stilin, formatimin, përputhshmërinë e markës, marketingun dhe strukturën.\nUdhëzimet e markës janë marrë parasysh dhe pikat kryesore janë kontrolluar.\n</think>\n"
    output = f"{thinking_placeholder}{report_data['output_json']}"
    
    return instruction, user_input, output

def format_full_text(instruction, user_input, output):
    """Combines components into the full Gemma-4 chat template string."""
    return (
        f"<start_of_turn>system\n{instruction}<end_of_turn>\n"
        f"<start_of_turn>user\n{user_input}<end_of_turn>\n"
        f"<start_of_turn>model\n{output}<end_of_turn>"
    )

def main():
    parser = argparse.ArgumentParser(description="Prepare Unsloth-compatible training data for Gemma-4.")
    repo_root = Path(__file__).parent.parent
    
    parser.add_argument("--input-dir", default=str(repo_root / "data" / "testset-1"), help="Input directory")
    parser.add_argument("--output", default=str(repo_root / "data" / "gemma4_analysis_unsloth.parquet"), help="Output Parquet")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"Error: {args.input_dir} not found.")
        return

    files = list(input_path.glob("*.json")) + [f for f in input_path.glob("*.txt") if f.suffix == ".txt"]
    
    dataset = []
    print(f"Processing {len(files)} files...")
    
    for f in files:
        try:
            # Basic JSON check for .txt files
            if f.suffix == ".txt":
                with open(f, 'r', encoding='utf-8') as check_f:
                    if check_f.read(1) != '{': continue
            
            report_data = load_json_report(f)
            instruction, user_input, output = get_unsloth_format(report_data)
            full_text = format_full_text(instruction, user_input, output)
            
            dataset.append({
                "id": report_data["id"],
                "instruction": instruction,
                "input": user_input,
                "output": output,
                "text": full_text
            })
        except Exception as e:
            print(f"Error in {f.name}: {e}")

    if not dataset:
        print("No data processed.")
        return

    df = pd.DataFrame(dataset)
    df.to_parquet(args.output, index=False, engine='pyarrow')
    
    print(f"\nSuccess! Created Unsloth-compatible data at: {args.output}")
    print(f"Columns: {list(df.columns)}")
    print(f"Total examples: {len(df)}")
    
    print("\n--- SAMPLE OUTPUT COLUMN ---")
    print(df.iloc[0]['output'])
    print("----------------------------")

if __name__ == "__main__":
    main()
