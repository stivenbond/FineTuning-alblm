import argparse
import json
import hashlib
from pathlib import Path
import os

def parse_args():
    parser = argparse.ArgumentParser(description="Process PWA feedback into DPO training pairs.")
    parser.add_argument("--raw-dir", default="data/rlhf/collected/", help="Directory of raw feedback JSON")
    parser.add_argument("--output", default="rlhf/dpo_pairs.jsonl", help="Output JSONL path")
    parser.add_argument("--min-pairs", type=int, default=150, help="Minimum pairs before writing")
    parser.add_argument("--teacher", action="store_true", help="Use teacher model to generate improved 'chosen' responses")
    return parser.parse_args()

def hash_input(inp_dict):
    s = json.dumps(inp_dict, sort_keys=True)
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def get_teacher_improvement(prompt):
    # Try using groq or anthropic
    if os.environ.get("GROQ_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=os.environ.get("GROQ_API_KEY")
            )
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            return None
    elif os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            return None
    elif os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return None
    return None

def main():
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    
    if not raw_dir.exists():
        print(f"Directory not found: {raw_dir}")
        return

    # Group by (input_hash, task, issue_index)
    feedback_groups = {}
    
    for filepath in raw_dir.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            inp = data.get("input")
            out = data.get("model_output")
            fb = data.get("feedback")
            
            if not inp or not out or not fb:
                continue
                
            rating = fb.get("rating")
            if rating not in ["unhelpful", "too_vague", "too_harsh"]:
                continue
                
            h = hash_input(inp)
            task = fb.get("task")
            idx = fb.get("issue_index")
            
            key = (h, task, idx)
            if key not in feedback_groups:
                feedback_groups[key] = {"input": inp, "output": out, "feedbacks": []}
            feedback_groups[key]["feedbacks"].append(fb)
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")

    pairs_generated = []
    needs_human = []
    
    needs_human_dir = Path("data/rlhf/needs_human_improvement")
    needs_human_dir.mkdir(parents=True, exist_ok=True)

    # Process filtered feedback
    import copy
    
    for (h, task_name, idx), group in feedback_groups.items():
        inp = group["input"]
        rejected_out = group["output"]
        
        # We need an improved 'chosen' output
        task_out = rejected_out.get(task_name, {})
        issues = task_out.get("issues", [])
        if not isinstance(issues, list) or idx >= len(issues):
            continue
            
        rejected_issue = issues[idx]
        rejected_guidance = rejected_issue.get("guidance", "")
        
        feedbacks = group["feedbacks"]
        reasons = [fb.get("rating") for fb in feedbacks]
        
        improved_guidance = None
        if args.teacher:
            prompt = (
                f"You are an expert Albanian editor. We gave a writer the following guidance for a '{task_name}' issue, "
                f"but they rated it as: {', '.join(reasons)}.\n\n"
                f"Original guidance: {rejected_guidance}\n\n"
                f"Context: The issue is of type '{rejected_issue.get('issue_type')}' at '{rejected_issue.get('location')}'.\n\n"
                f"Provide a better, clearer, and more helpful guidance in Albanian. "
                f"IMPORTANT: The guidance must be instructional only — never rewrite the text for them. "
                f"Output ONLY the new guidance string, nothing else."
            )
            improved_guidance = get_teacher_improvement(prompt)

        if improved_guidance:
            chosen_out = copy.deepcopy(rejected_out)
            chosen_out[task_name]["issues"][idx]["guidance"] = improved_guidance
            pairs_generated.append({
                "input": inp,
                "chosen": chosen_out,
                "rejected": rejected_out
            })
        else:
            human_task = {
                "input": inp,
                "task_name": task_name,
                "issue_index": idx,
                "rejected_guidance": rejected_guidance,
                "reasons": reasons,
                "original_output": rejected_out
            }
            needs_human.append(human_task)

    # Stats
    print(f"Total DPO pairs ready: {len(pairs_generated)}")
    print(f"Total pairs needing human improvement: {len(needs_human)}")
    
    if len(pairs_generated) >= args.min_pairs:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # append only
        with open(out_path, "a", encoding="utf-8") as f:
            for pair in pairs_generated:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        print(f"Appended {len(pairs_generated)} pairs to {out_path}")
    else:
        print(f"Not writing to DPO file. Have {len(pairs_generated)} pairs, need {args.min_pairs}.")
        
    if needs_human:
        for i, ht in enumerate(needs_human):
            out_f = needs_human_dir / f"human_task_{h}_{ht['task_name']}_{ht['issue_index']}.json"
            with open(out_f, "w", encoding="utf-8") as f:
                json.dump(ht, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
