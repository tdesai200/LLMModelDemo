# claude_icd10_classifier.py
# ICD-10 Clinical Note Classifier with Multiple Prompt Modes (A/B/C/D/E)
# Requires: pip install anthropic pandas python-dotenv

import os
import re
import time
import json
import argparse
import pandas as pd
try:
    from anthropic import Anthropic
except ImportError:
    raise SystemExit('Please install the Anthropic SDK: pip install anthropic')


# ---------------------------------------------------------------
# CLI ARGUMENTS
# ---------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser(description="ICD-10 LLM Classifier with Prompt Options")
    parser.add_argument(
        "--prompt",
        type=str,
        default="A",
        help="Choose prompt style: A=baseline, B=strong, C=reasoning+JSON, "
             "D=disambiguation, E=chain-of-thought"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=250,
        help="Number of notes to evaluate (default=250)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/synthetic_icd10_notes_500.csv",
        help="Path to dataset CSV file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/predictions.csv",
        help="Output file for predictions (default = results/predictions.csv)"
    )
    return parser.parse_args()


# ---------------------------------------------------------------
# PROMPT VERSIONS
# ---------------------------------------------------------------

PROMPT_A = (
    "You are an expert medical coder. "
    "Assign exactly ONE ICD-10 diagnosis code that best represents the main condition. "
    "Return ONLY JSON: {\"code\": \"...\", \"description\": \"...\"}"
)

PROMPT_B = (
    "You are a certified ICD-10 medical coding specialist. "
    "Select ONE ICD-10 diagnosis code that reflects the PRIMARY diagnosis only. "
    "Ignore unrelated findings. "
    "Return valid JSON: {\"code\": \"...\", \"description\": \"...\"}"
)

PROMPT_C = (
    "You are a medical coder. "
    "First provide a one-sentence reason for your choice. "
    "Then return JSON on a new line: {\"code\": \"...\", \"description\": \"...\"}"
)

PROMPT_D = (
    "You are an ICD-10 coding expert. "
    "Carefully distinguish between conditions with similar symptoms "
    "(such as pneumonia vs bronchitis). "
    "Return ONLY JSON: {\"code\": \"...\", \"description\": \"...\"}"
)

# ---------------------------------------------------------------
# NEW PROMPT E — Unified Chain-of-Thought Prompt
# ---------------------------------------------------------------

PROMPT_E = (
    "You are an expert medical coder. Your job is to read a clinical note and assign the "
    "single best ICD-10 diagnosis code.\n\n"
    "Follow this reasoning process BEFORE generating your final answer:\n"
    "1. Identify the main clinical problem the note is describing.\n"
    "2. Ignore unrelated or minor symptoms that are not central to the diagnosis.\n"
    "3. If symptoms overlap between similar conditions (e.g., bronchitis vs pneumonia, "
    "asthma vs COPD, chest pain vs shortness of breath), briefly explain how you "
    "distinguished between them.\n"
    "4. Use only information clearly stated in the note do not guess details.\n"
    "5. After your reasoning, output ONLY one ICD-10 code and its description in JSON.\n\n"
    "Format your response EXACTLY as:\n"
    "Reason: <brief explanation>\n"
    "{\"code\": \"XXX.XX\", \"description\": \"<ICD-10 label>\"}"
)


def choose_system_prompt(version):
    version = version.upper()
    if version == "A":
        return PROMPT_A
    if version == "B":
        return PROMPT_B
    if version == "C":
        return PROMPT_C
    if version == "D":
        return PROMPT_D
    if version == "E":
        return PROMPT_E
    return PROMPT_A  # fallback


# ---------------------------------------------------------------
# JSON EXTRACTION
# ---------------------------------------------------------------

def extract_json(text):
    match = re.search(r'\{.*?\}', text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------
# BUILD USER PROMPT
# ---------------------------------------------------------------

def build_user_prompt(note_text, candidate_codes=None):
    base = f"Clinical note:\n\n{note_text}\n\n"

    if candidate_codes:
        base += "Choose the best code from the following list:\n"
        for c, d in candidate_codes:
            base += f"- {c}: {d}\n"

    base += "\nReturn JSON only."
    return base


# ---------------------------------------------------------------
# CLAUDE INFERENCE
# ---------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise SystemExit("ERROR: Please set ANTHROPIC_API_KEY environment variable.")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

def predict_code(note_text, prompt_version, candidate_codes=None,
                 max_retries=3, sleep=1.5):

    system_prompt = choose_system_prompt(prompt_version)
    user_prompt = build_user_prompt(note_text, candidate_codes)

    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            out = ""
            for block in msg.content:
                if block.type == "text":
                    out += block.text

            data = extract_json(out)

            if data and "code" in data and "description" in data:
                return data["code"].strip(), data["description"].strip(), out

        except Exception as e:
            if attempt == max_retries - 1:
                return None, None, f"ERROR: {str(e)}"

            time.sleep(sleep)

    return None, None, "ERROR: Exhausted retries"


# ---------------------------------------------------------------
# EVALUATION FUNCTION
# ---------------------------------------------------------------

def evaluate(csv_path, sample_size, prompt_version, output_file, candidate_mode=True):
    df = pd.read_csv(csv_path)
    if sample_size > len(df):
        sample_size = len(df)

    eval_df = df.sample(n=sample_size, random_state=42).copy()

    candidate_codes = None
    if candidate_mode:
        freq = df["icd10_code"].value_counts().head(20).index.tolist()
        code_map = df.drop_duplicates("icd10_code").set_index("icd10_code")["icd10_desc"].to_dict()
        candidate_codes = [(c, code_map.get(c, "")) for c in freq]

    preds = []
    correct = 0

    print("\nRunning evaluation...\n")

    for _, row in eval_df.iterrows():
        pred_code, pred_desc, raw = predict_code(
            row["note_text"],
            prompt_version,
            candidate_codes=candidate_codes
        )

        is_correct = (pred_code == row["icd10_code"])
        preds.append({
            "note_id": row["note_id"],
            "gold_code": row["icd10_code"],
            "gold_desc": row["icd10_desc"],
            "pred_code": pred_code,
            "pred_desc": pred_desc,
            "raw_response": raw,
            "correct": is_correct
        })

        if is_correct:
            correct += 1

    out_df = pd.DataFrame(preds)
    accuracy = correct / len(out_df) if len(out_df) else 0.0

    out_df.to_csv(output_file, index=False)

    print(f"Evaluated {len(out_df)} notes.")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Predictions saved to {output_file}\n")

    return out_df, accuracy


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------

if __name__ == "__main__":
    args = get_args()

    prompt_choice = args.prompt.upper()
    print(f"\nUsing prompt version: {prompt_choice}")
    print(f"Evaluating {args.sample_size} notes...")
    print(f"Dataset: {args.csv}\n")

    evaluate(
        csv_path=args.csv,
        sample_size=args.sample_size,
        prompt_version=prompt_choice,
        output_file=args.output,
        candidate_mode=True
    )
