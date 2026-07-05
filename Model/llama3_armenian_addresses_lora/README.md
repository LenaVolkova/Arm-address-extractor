---
base_model: unsloth/meta-llama-3.1-8b-instruct-bnb-4bit
library_name: peft
pipeline_tag: text-generation
tags:
- base_model:adapter:unsloth/meta-llama-3.1-8b-instruct-bnb-4bit
- lora
- sft
- transformers
- trl
- unsloth
- armenian
- address-extraction
---

# Llama 3.1 8B Instruct - Armenian Address Extraction (LoRA)

This is a LoRA adapter model fine-tuned on top of `unsloth/meta-llama-3.1-8b-instruct-bnb-4bit` to perform structured address extraction from raw, unstructured Armenian texts (such as planned utility maintenance announcements). 

It extracts details including region, city, settlement type, district, street name, and building lists, and formats the output strictly as a JSON array.

## Model Details

### Model Description

- **Developed by:** Elena Volkova
- **Language(s) (NLP):** Armenian (`hy`)
- **License:** MIT
- **Finetuned from model:** `unsloth/meta-llama-3.1-8b-instruct-bnb-4bit`
- **Finetuning Tool:** Unsloth (2026.6.9)

### Model Sources

- **Repository:** Hugging Face Model Hub (Adapter weights only)
- **Finetuning Notebook:** `Model/Finetuning/addrfitmodel.ipynb`

---

## Uses

### Direct Use

This model is fine-tuned to extract structured address components from Armenian texts. Given an unstructured announcement, it parses the locations and outputs them as a clean JSON array.

#### Expected Output Fields:
- `region`: Province or region (մարզ) name.
- `cityname`: City or village name.
- `citytype`: Settlement type (`քաղաք` / `գյուղ`).
- `district`: District/neighborhood.
- `street`: Street name.
- `bldnum`: Specific building number.
- `bldlist`: Ranges or list of building numbers.

### Out-of-Scope Use

- Processing address queries or extraction in languages other than Armenian.
- General instruction-following or conversation unrelated to address parsing.
- Geocoding coordinates (latitude/longitude), which requires downstream geographic lookup databases.

---

## Bias, Risks, and Limitations

- **Domain Bias:** The training data is primarily composed of public utility outage alerts (such as power maintenance records). The model may perform less optimally on other types of Armenian texts (e.g. historical addresses, informal social media posts, or international shipping labels).
- **Geographic Bias:** Address naming patterns reflect contemporary Armenian municipal divisions (e.g., heavily represented by Yerevan districts and municipal centers).

### Recommendations

For downstream systems, it is recommended to set a low temperature (e.g., `0.1`) during generation to ensure that the output remains strictly valid JSON and adheres strictly to the input context.

---

## How to Get Started with the Model

You can load and run the adapter using `unsloth` and `transformers`:

```python
import json
from unsloth import FastLanguageModel

max_seq_length = 1024
dtype = None
load_in_4bit = True

# 1. Load model and tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "LenaVolkova/llama-3.1-8b-armenian-address-extraction-lora", 
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)
FastLanguageModel.for_inference(model)

# 2. Define prompt structure matching training format
SYSTEM_PROMPT = (
    "You are a helpful assistant that extracts addresses from Armenian text "
    "and returns them strictly in JSON format with the following fields: "
    "region, cityname, citytype, district, street, bldnum, bldlist"
)

def extract_address(armenian_text):
    prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{SYSTEM_PROMPT}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n\nИзвлеки адрес из следующего текста:\n{armenian_text}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    
    inputs = tokenizer([prompt], return_tensors = "pt").to("cuda")
    outputs = model.generate(
        **inputs,
        max_new_tokens = 1024,
        use_cache = True,
        temperature = 0.1,
        top_p = 0.9
    )
    
    generated_tokens = outputs[0][inputs.input_ids.shape[1]:]
    response_text = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return response_text

# Example execution
text = "Ես ապրում եմ Հայաստանում, Երևան քաղաքում, Ամիրյան փողոց, շենք 4"
print(extract_address(text))
#Expected result: [{'region': 'Երևան', 'cityname': 'Երևան', 'citytype': 'քաղաք', 'district': 'Աջափնյակ', 'street': 'Ամիրյան փողոց', 'bldnum': '4', 'bldlist': None}]
```

---

## Training Details

### Training Data

The model was trained on a curated dataset of Armenian utility alerts. The dataset was split into:
- **Train dataset:** 808 records
- **Test/Validation dataset:** 90 records
- **Format:** Llama 3.1 Instruct Chat template containing a custom system prompt and a target JSON array serialization.

### Training Procedure

- **Hardware:** NVIDIA A100-SXM4-80GB (1 GPU)
- **Epochs:** 1 (completed over 100 training steps)
- **Time taken:** 3 minutes and 16 seconds

#### Training Hyperparameters

- **Optimizer:** `adamw_8bit`
- **Learning Rate:** 2e-4
- **Learning Rate Scheduler:** `linear`
- **Warmup Steps:** 5
- **Weight Decay:** 0.01
- **Batch Size per device:** 2
- **Gradient Accumulation Steps:** 4
- **Total Batch Size:** 8 (2 x 4 x 1)
- **Precision:** `bf16` (Bfloat16 enabled)
- **LoRA Config:**
  - Rank (r): 16
  - Alpha: 16
  - Target Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
  - Bias: `none`

#### Training Loss Progression
The model loss converged steadily over 100 steps:
- **Step 1:** 1.588
- **Step 10:** 0.697
- **Step 30:** 0.172
- **Step 50:** 0.146
- **Step 80:** 0.167
- **Step 100:** 0.085

---

## Technical Specifications

### Compute Infrastructure

- **Hardware:** Single NVIDIA A100-SXM4-80GB (Max memory: 79.251 GB)
- **Software Stack:** Linux, PyTorch 2.11.0+cu128, CUDA 8.0 / 12.8, Triton 3.6.0
- **Framework versions:**
  - PEFT 0.19.1
  - Unsloth 2026.6.9
  - Transformers 5.5.0
  - TRL 0.12.0