# ml/: training in Google Colab, serving in the backend

```
Colab notebook  --exports-->  artifact bundle (a folder)  --unzip into-->  ml/artifacts/  --loaded by-->  backend
```

| Path | Purpose |
|---|---|
| `notebooks/motor_condition_ann_training.ipynb` | The training notebook (Option A: condition classification). Run it in Google Colab. |
| `scripts/validate_artifacts.py` | Checks a bundle with the backend's own loader before you start the app. |
| `artifacts/` | Put the unzipped bundle here. **Git ignores everything in this folder.** |

## The bundle contract
The notebook writes a folder `pm_condition_ann_v<version>/` containing `MANIFEST.json` (SHA-256 of every file), `preprocessing.json`
(feature order, scaler mean/scale), `feature_schema.json`, `class_mapping.json`, `model_architecture.json`, `weights.npz`,
`training_metadata.json`, `parity_probe.json`, plus `model.keras`, `model_card.md` and `reproducibility_report.md`.
The backend uses only JSON and NumPy arrays (no pickle). The full contract and its known gaps are in `docs/artifact-contract.md`.

## Steps (Windows PowerShell)
1. Run the notebook in Colab and download `pm_condition_ann_v1.0.0.zip`.
2. Unzip into the project:
   ```powershell
   Expand-Archive -Path "$HOME\Downloads\pm_condition_ann_v1.0.0.zip" -DestinationPath ".\ml\artifacts" -Force
   ```
   (If a `__pycache__` folder appears inside the bundle, delete it. It is harmless and ignored by the loader.)
3. Check it:
   ```powershell
   python ml/scripts/validate_artifacts.py
   ```
4. Start the backend (see the root README). If the bundle is missing or invalid, the backend **refuses to start** and prints why.

## Data safety
Never commit datasets, bundles or notebooks with outputs. `.gitignore` blocks `*.csv`, `ml/artifacts/*`, model files and databases.
In Colab use *Edit, Clear all outputs* before saving a copy to GitHub.
