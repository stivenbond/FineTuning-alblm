import argparse
import json
import os
from pathlib import Path
import time
import logging
from dotenv import load_dotenv

# Find workspace root (up 3 levels from models/name/scripts/)
workspace_root = Path(__file__).parent.parent.parent.parent
load_dotenv(workspace_root / ".env")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic training examples.")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--seed-dir", default=str(repo_root / "data" / "seed"), help="Path to seed .txt articles")
    parser.add_argument("--register", required=True, choices=["editorial", "informational", "marketing", "classical", "mixed", "all"])
    parser.add_argument("--model", default="claude", help="Model to use: claude, gpt-4o, or groq model name like groq/llama3-70b-8192")
    parser.add_argument("--per-article", type=int, default=3)
    parser.add_argument("--guidelines", help="Path to brand guidelines JSON")
    parser.add_argument("--key-points", help="Path to a .txt file with key points")
    parser.add_argument("--output-dir", default=str(repo_root / "data" / "raw_synthetic"), help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without API calls")
    parser.add_argument("--manual", action="store_true", help="Generate scaffolding for manual insertion instead of calling API")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls")
    return parser.parse_args()

def get_next_id(output_dir, register):
    counter_file = Path(output_dir) / "id_counter.txt"
    current_id = 1
    if counter_file.exists():
        with open(counter_file, "r") as f:
            content = f.read().strip()
            if content:
                current_id = int(content) + 1
    with open(counter_file, "w") as f:
        f.write(str(current_id))
    return f"alb-{register}-{current_id:04d}"

def call_api(prompt, model, temp=0.8):
    if model.startswith("groq/"):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY")
        )
        model_name = model.split("groq/")[1]
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temp
        )
        return response.choices[0].message.content
    elif "gpt" in model:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temp
        )
        return response.choices[0].message.content
    else:
        # Default Claude
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4000,
            temperature=temp,
            messages=[{"role": "user", "content": prompt + "\n\nPlease output valid JSON only."}]
        )
        return response.content[0].text

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    import sys
    sys.path.append(str(Path(__file__).parent))
    from build_prompt import parse_response

    registers = ["editorial", "informational", "marketing", "classical", "mixed"] if args.register == "all" else [args.register]
    schema_path = repo_root / "schemas" / "training_example_v1.json"
    if not schema_path.exists():
        logging.error("Schema file missing.")
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_content = f.read()

    guidelines_content = ""
    if args.guidelines and Path(args.guidelines).exists():
        with open(args.guidelines, "r", encoding="utf-8") as f:
            guidelines_content = f.read()

    key_points_content = ""
    key_points_list = []
    if args.key_points and Path(args.key_points).exists():
        with open(args.key_points, "r", encoding="utf-8") as f:
            key_points_list = [line.strip() for line in f if line.strip()]
            key_points_content = "\n".join(key_points_list)

    for reg in registers:
        seed_dir = Path(args.seed_dir) / reg
        if not seed_dir.exists():
            continue

        prompt_path = repo_root / "prompts" / f"generate_synthetic_{reg}.txt"
        if not prompt_path.exists():
            logging.warning(f"Prompt template missing for {reg}")
            continue
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        out_dir = Path(args.output_dir) / reg
        out_dir.mkdir(parents=True, exist_ok=True)
        failed_dir = Path(args.output_dir) / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        for filepath in seed_dir.glob("*.txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                article_text = f.read()
            
            prompt = prompt_template.replace("{brand_guidelines}", guidelines_content)
            prompt = prompt.replace("{key_points}", key_points_content)
            prompt = prompt.replace("{article_text}", article_text)
            prompt = prompt.replace("{schema}", schema_content)

            variants = 1 if args.manual else args.per_article

            for i in range(variants):
                example_id = get_next_id(args.output_dir, reg)
                out_file = out_dir / f"{example_id}.json"

                if args.dry_run:
                    logging.info(f"[DRY RUN] Would process {filepath.name} -> {example_id}")
                    continue
                
                if args.manual:
                    scaffold = {
                        "id": example_id,
                        "metadata": {
                            "register": reg,
                            "annotator": "human",
                            "rlhf_eligible": True,
                            "version": "1.0.0",
                            "reviewer": "",
                            "reviewed_at": ""
                        },
                        "input": {
                            "brand_guidelines": guidelines_content,
                            "key_points": key_points_list,
                            "article_text": article_text
                        },
                        "output": {
                            "_instruction": "FILL IN MANUALLY ACCORDING TO SCHEMA"
                        }
                    }
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(scaffold, f, indent=2, ensure_ascii=False)
                    logging.info(f"Created manual scaffold {out_file}")
                    continue

                logging.info(f"Calling API for {filepath.name} variant {i+1}...")
                try:
                    response_text = call_api(prompt, args.model, temp=0.8)
                except Exception as e:
                    logging.error(f"API call failed: {e}")
                    continue

                try:
                    data = parse_response(response_text)
                    if data.get("parse_error"):
                        raise ValueError("Failed to parse JSON")
                    
                    data["id"] = example_id
                    data["metadata"]["annotator"] = "synthetic"
                    data["metadata"]["register"] = reg
                    
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    logging.info(f"Saved {out_file}")
                except Exception as e:
                    logging.warning(f"Failed to parse JSON, retrying... ({e})")
                    try:
                        retry_prompt = prompt + "\n\nProvide ONLY the valid JSON, no markdown formatting. Do not use <think> blocks this time."
                        response_text = call_api(retry_prompt, args.model, temp=0.3)
                        data = parse_response(response_text)
                        if data.get("parse_error"):
                            raise ValueError("Retry failed to parse JSON")
                        data["id"] = example_id
                        data["metadata"]["annotator"] = "synthetic"
                        data["metadata"]["register"] = reg
                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        logging.info(f"Saved {out_file} on retry")
                    except Exception as e2:
                        logging.error(f"Retry failed. Saving to failed dir. ({e2})")
                        with open(failed_dir / f"failed_{example_id}.txt", "w", encoding="utf-8") as f:
                            f.write(response_text)
                
                time.sleep(args.delay)

if __name__ == "__main__":
    main()
