import argparse
import json
import os
from pathlib import Path
import time
import logging
import random
from dotenv import load_dotenv

# Find workspace root (up 3 levels from models/name/scripts/)
workspace_root = Path(__file__).parent.parent.parent.parent
load_dotenv(workspace_root / ".env")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic teacher diary training examples.")
    repo_root = Path(__file__).parent.parent
    parser.add_argument("--output-dir", default=str(repo_root / "data" / "raw_synthetic"), help="Output directory")
    parser.add_argument("--per-article", type=int, default=5)
    parser.add_argument("--model", default="claude-3-opus-20240229", help="Teacher model")
    return parser.parse_args()

def get_next_id(output_dir):
    counter_file = Path(output_dir) / "id_counter.txt"
    current_id = 1
    if counter_file.exists():
        with open(counter_file, "r") as f:
            content = f.read().strip()
            if content:
                current_id = int(content) + 1
    with open(counter_file, "w") as f:
        f.write(str(current_id))
    return f"td-{current_id:04d}"

def call_api(prompt, model):
    # Simplified for the demonstration
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Example field sets a user might define
FIELD_SETS = [
    ["Summary", "Homework", "Engagement"],
    ["Lënda", "Përmbledhja", "Detyrat", "Mungesat"],
    ["Topic", "Key Points", "Student Feedback", "Action Items"],
    ["Data", "Klasa", "Objektivat e arritura", "Vërejtje"]
]

CONTEXT_TEMPLATES = [
    "Lesson: {subject}. Students present: {students}. Main topic: {topic}. Notes: {notes}.",
    "Sot zhvilluam lëndën {subject} me temë {topic}. Klasa ishte {engagement}. Shënime: {notes}."
]

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    repo_root = Path(__file__).parent.parent
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sys_prompt = "You are a teacher diary expert. Generate a realistic training example for a generator model."

    for i in range(args.per_article):
        example_id = get_next_id(args.output_dir)
        fields = random.choice(FIELD_SETS)
        
        # In a real scenario, we'd use a teacher model to generate the 'input' and 'output' pair
        # For this script, we'll just scaffold it or call the API to generate one full training JSON
        
        prompt = f"""Generate a training JSON for a Teacher Diary Generator.
Base the diary on:
Subject: Mathematics
Topic: Integrals
Engagement: Mixed
Notes: Some students struggled with the power rule.

Fields requested by user: {fields}

The output must be a JSON following this structure:
{{
  "id": "{example_id}",
  "metadata": {{ "version": "1.0.0", "generated_at": "2026-04-29T10:00:00Z" }},
  "input": {{
    "context": {{ ... }},
    "target_fields": {fields}
  }},
  "output": {{
    "entry": {{ ... filled with generated content for the fields ... }},
    "tool_calls": [ ... optional tool call if notes imply it ... ]
  }}
}}
"""
        logging.info(f"Generating example {example_id}...")
        # response = call_api(prompt, args.model)
        # ... logic to save response ...

if __name__ == "__main__":
    main()
