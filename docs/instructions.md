# Project Instructions: clinical_notes_classifier_LLM.py

This file explains how to run the demo `src/clinical_notes_classifier_LLM.py` which classifies synthetic clinical notes into a single ICD-10 diagnosis code using the Anthropic Claude API.

Prerequisites
- Python 3.8+ (using 3.14 here)
- Install dependencies:

```powershell
pip install anthropic pandas python-dotenv
```

- Set your Anthropic API key (Windows PowerShell):

```powershell
setx ANTHROPIC_API_KEY "YOUR_ACTUAL_API_KEY"
```

Restart your terminal after setting the env var.

- Ensure dataset exists at `data/synthetic_icd10_notes_500.csv` with columns: `note_id`, `note_text`, `icd10_code`, `icd10_desc`.
- Create output directory if missing:

```powershell
mkdir results -Force
```

What the script does
- Loads the dataset CSV, samples N notes (default 250), calls Anthropic Claude with a chosen prompt version (A–E), extracts JSON with `code` and `description`, saves predictions and computes accuracy.

Location
- Script: `src/clinical_notes_classifier_LLM.py`

Command-line arguments
- `--prompt` : Prompt version to use. Options: `A`, `B`, `C`, `D`, `E`. Default: `A`.
- `--sample-size` : Number of notes to evaluate (default `250`). Script caps sample at dataset size.
- `--csv` : Path to input CSV. Default: `data/synthetic_icd10_notes_500.csv`.
- `--output` : Output CSV path. Default: `results/predictions.csv`.

Basic usage (PowerShell)

```powershell
python src\clinical_notes_classifier_LLM.py
```

Examples

Run prompt D with 400 samples and save:

```powershell
python src\clinical_notes_classifier_LLM.py --prompt D --sample-size 400 --output results\prediction_D.csv
```

Run chain-of-thought prompt E for 100 samples:

```powershell
python src\clinical_notes_classifier_LLM.py --prompt E --sample-size 100 --output results\prediction_E.csv
```

Run all prompts (short sample) for comparison:

```powershell
python src\clinical_notes_classifier_LLM.py --prompt A --sample-size 50 --output results\pred_A.csv
python src\clinical_notes_classifier_LLM.py --prompt B --sample-size 50 --output results\pred_B.csv
python src\clinical_notes_classifier_LLM.py --prompt C --sample-size 50 --output results\pred_C.csv
python src\clinical_notes_classifier_LLM.py --prompt D --sample-size 50 --output results\pred_D.csv
python src\clinical_notes_classifier_LLM.py --prompt E --sample-size 50 --output results\pred_E.csv
```

Output
- The output CSV contains these columns: `note_id`, `gold_code`, `gold_desc`, `pred_code`, `pred_desc`, `raw_response`, `correct`.
- The script prints the number evaluated and accuracy percentage.

Troubleshooting
- "ERROR: Please set ANTHROPIC_API_KEY environment variable": set the `ANTHROPIC_API_KEY` env var and restart PowerShell.
- FileNotFoundError for dataset: verify `--csv` path or place CSV at `data/synthetic_icd10_notes_500.csv`.
- If `results` file error occurs, create the `results/` directory.
- API/network issues: script retries up to 3 times with delays; reduce `--sample-size` or retry later if rate-limited.

Notes
- Model used in the script: Claude 3 Haiku via Anthropic SDK; temperature is set to `0.0` for deterministic outputs.
- Candidate mode: script presents the top-20 most frequent ICD-10 codes as candidate choices by default.
- Sampling is reproducible with `random_state=42`.

Quick run checklist
```powershell
pip install anthropic pandas python-dotenv
setx ANTHROPIC_API_KEY "YOUR_ACTUAL_API_KEY"
mkdir results -Force
python src\clinical_notes_classifier_LLM.py --prompt A --sample-size 250 --output results\predictions.csv
```

