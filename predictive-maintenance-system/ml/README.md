# ml/ — Training in Google Colab, serving in the backend

This folder is the **bridge** between your Colab notebook (where you train) and the
FastAPI backend (where predictions are served).

```
Colab notebook  --export_artifacts()-->  3 files  --copy-->  ml/artifacts/  --loaded by-->  backend
```

## What is in here

| Path | Purpose |
|---|---|
| `notebooks/01_train_and_export_template.ipynb` | Colab template. Contains **no data and no results**; you fill in the TODO cells. |
| `scripts/export_artifacts.py` | Helper that writes the 3 artifact files. Already pasted inside the notebook. |
| `scripts/validate_artifacts.py` | Run on your laptop to check the files load before starting the app. |
| `feature_schema.example.json` | Shows the format of the feature list. |
| `model_metadata.example.json` | Shows the format of the model metadata. |
| `artifacts/` | Where you put the 3 exported files. **Git ignores everything here** (only `.gitkeep` is tracked). |

## The 3 artifact files (the "contract")

1. **`model.joblib`** — one scikit-learn `Pipeline` that includes scaling/encoding **and** the classifier. It must support `predict_proba()`.
2. **`feature_schema.json`** — the feature names (in training order), with optional `unit`, `min`, `max`, `description`.
3. **`model_metadata.json`** — `model_name`, `model_version`, `positive_class` (the label meaning "failure"), optional `decision_threshold`.

## Rules that prevent the most common beginner bugs

1. **Train on a pandas DataFrame, not a NumPy array.** The exporter refuses arrays, because column names and order must be recorded.
2. **Put preprocessing inside the Pipeline.** Then the backend cannot accidentally preprocess differently from training.
3. **Same scikit-learn version in Colab and the backend.** Colab prints its version in the first notebook cell; make `backend/requirements.txt` match the same minor version (e.g. `1.6.x`). A mismatch can break loading.
4. **Choose `decision_threshold` on validation data**, never on the test set.
5. **Only add `min`/`max` limits that come from your dataset or a domain expert.** The backend will reject readings outside them, so wrong limits would wrongly block real inputs. Leave them out if unsure.

## Data safety

- Never commit datasets or model files. `.gitignore` blocks `*.csv`, `*.joblib`, `ml/artifacts/*` and more.
- **Clear notebook outputs before committing** a notebook (Colab: *Edit → Clear all outputs*), because outputs can contain data rows.
- Keep confidential data on Google Drive / Colab only.

## Step by step (Windows PowerShell)

1. Open the template notebook in Google Colab (upload it, or open from GitHub).
2. Fill in the TODO cells, train, and run the export cell.
3. Download `artifacts.zip` from Colab and unzip it into `ml\artifacts\`:
   ```powershell
   Expand-Archive -Path "$HOME\Downloads\artifacts.zip" -DestinationPath ".\ml\artifacts" -Force
   ```
4. Check the files load:
   ```powershell
   python ml/scripts/validate_artifacts.py
   ```
   Expect `Smoke test OK`. (The smoke-test number is a placeholder input, **not** a research result.)
5. Restart the backend. `http://localhost:8000/api/v1/model/info` should now say `"model_ready": true`.

## Sharing the model for the viva deployment

The model file is not in GitHub. See `docs/deployment.md` for how to get it onto the hosted backend.
