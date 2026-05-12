# Exporting to GGUF for CPU Deployment

## Step 1: Merge LoRA adapter into base model
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("google/gemma-4-1b-it")
model = PeftModel.from_pretrained(base, "training/final")
merged = model.merge_and_unload()
merged.save_pretrained("training/merged")
AutoTokenizer.from_pretrained("google/gemma-4-1b-it").save_pretrained("training/merged")
```

## Step 2: Convert to GGUF
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && pip install -r requirements.txt
python convert_hf_to_gguf.py ../training/merged --outfile ../training/final/albanian-editor.gguf
```

## Step 3: Quantize to Q4_K_M (best quality/size tradeoff for CPU)
```bash
./llama-quantize ../training/final/albanian-editor.gguf \
                 ../training/final/albanian-editor-q4km.gguf Q4_K_M
```

## Step 4: Test on CPU
```bash
./llama-cli -m ../training/final/albanian-editor-q4km.gguf \
            -p "$(cat test_prompt.txt)" \
            --temp 0.1 -n 2048
```

## Expected file sizes
- 1B model Q4_K_M: ~700MB
- 4B model Q4_K_M: ~2.5GB

## Expected CPU inference times (per ~500 word article)
- 1B Q4_K_M on 8-core CPU: ~8–15 seconds
- 4B Q4_K_M on 8-core CPU: ~25–45 seconds
