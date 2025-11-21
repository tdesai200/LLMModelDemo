# claude_icd10_classifier.py
# Demo: Classify synthetic clinical notes into a single ICD-10 code using Claude 3 Haiku
# Requires: pip install anthropic pandas python-dotenv

import os
import re
import time
import pandas as pd

try:
    from anthropic import Anthropic
except ImportError:
    raise SystemExit('Please install the Anthropic SDK: pip install anthropic')

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not ANTHROPIC_API_KEY:
    print('Set your API key first: setx ANTHROPIC_API_KEY YOUR_KEY (Windows) or export ANTHROPIC_API_KEY=YOUR_KEY (macOS/Linux)')

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    'You are an expert medical coder. '
    'Your task is to assign the single most appropriate ICD-10 diagnosis code (not procedure) '
    'for the given clinical note. '
    'Return ONLY this JSON with two keys: code and description. '
    'Example: {"code": "I10", "description": "Essential (primary) hypertension"}'
)

SYSTEM_PROMPT_2 = (
    'You are a medical coder. '
    'Assign one ICD-10 diagnosis code and rate your confidence from 0–100%. '
    'Return JSON : '
    '{"code": "...", "description": "...", "confidence": 0–100}'
)

def build_user_prompt(note_text, candidate_codes=None):
    base = 'Clinical note:\n\n' + note_text + '\n\n'
    if candidate_codes:
        base += 'Choose the best code from this candidate list:\n'
        for c, d in candidate_codes:
            base += f'- {c} : {d}\n'
    base += '\nReturn JSON only.'
    return base

def extract_json(text):
    match = re.search(r'\{.*?\}', text, flags=re.DOTALL)
    if not match:
        return None
    try:
        import json
        return json.loads(match.group(0))
    except Exception:
        return None

def predict_code(note_text, candidate_codes=None, max_retries=3, sleep=1.5):
    user_prompt = build_user_prompt(note_text, candidate_codes)
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model='claude-3-haiku-20240307',
                max_tokens=180,
                temperature=0.0,
                system=SYSTEM_PROMPT_2,
                messages=[{'role': 'user', 'content': user_prompt}],
            )
            out = ''
            for block in msg.content:
                if block.type == 'text':
                    out += block.text
            data = extract_json(out)
            if data and 'code' in data and 'description' in data:
                return data['code'].strip(), data['description'].strip(), out
        except Exception as e:
            err = str(e)
            if attempt == max_retries - 1:
                return None, None, f'ERROR: {err}'
            time.sleep(sleep)
    return None, None, 'ERROR: Exhausted retries'

def evaluate(csv_path='data/synthetic_icd10_notes_500.csv', sample_size=100, candidate_mode=True):
    df = pd.read_csv(csv_path)
    eval_df = df.sample(n=sample_size, random_state=42).copy()
    candidate_codes = None
    if candidate_mode:
        freq = df['icd10_code'].value_counts().head(20).index.tolist()
        code_map = df.drop_duplicates('icd10_code').set_index('icd10_code')['icd10_desc'].to_dict()
        candidate_codes = [(c, code_map.get(c, '')) for c in freq]

    preds = []
    correct = 0
    for _, row in eval_df.iterrows():
        pred_code, pred_desc, raw = predict_code(row['note_text'], candidate_codes=candidate_codes)
        is_correct = (pred_code == row['icd10_code'])
        preds.append({
            'note_id': row['note_id'],
            'gold_code': row['icd10_code'],
            'gold_desc': row['icd10_desc'],
            'pred_code': pred_code,
            'pred_desc': pred_desc,
            'raw_response': raw,
            'correct': is_correct
        })
        if is_correct:
            correct += 1

    out_df = pd.DataFrame(preds)
    accuracy = correct / len(out_df) if len(out_df) else 0.0
    out_df.to_csv('results/predictions.csv', index=False)
    print(f'Evaluated {len(out_df)} notes. Accuracy: {accuracy:.2%}')
    print('Wrote predictions to results/predictions.csv')
    return out_df, accuracy

if __name__ == '__main__':
    evaluate(csv_path='data/synthetic_icd10_notes_500.csv', sample_size=100, candidate_mode=True)