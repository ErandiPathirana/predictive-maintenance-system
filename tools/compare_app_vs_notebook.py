"""Task 10: do the DEPLOYED app and the validation notebook give the same answer for the same records?
Usage:  python compare_app_vs_notebook.py <app_export.csv> <validation_outputs/test_predictions.csv> [--tol 5e-6]
 app_export.csv   : the CSV exported from the web app's History page (columns record_id, predicted_condition, model_score_Normal/Alert/Danger)
 test_predictions : written by pm_model_validation.py (columns record_id, pred, p_Normal, p_Alert, p_Danger; pred is 0/1/2)
The app writes scores with 6 decimals, so a tolerance of about 5e-6 is expected. Needs pandas only. Nothing is modified."""
import sys
import pandas as pd

CLASSES = ["Normal", "Alert", "Danger"]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 5e-6
if "--tol" in sys.argv: args.remove(sys.argv[sys.argv.index("--tol") + 1])
if len(args) != 2: sys.exit(__doc__)
app = pd.read_csv(args[0]); nb = pd.read_csv(args[1])
for need, df, name in [(["record_id", "predicted_condition", *[f"model_score_{c}" for c in CLASSES]], app, "app export"),
                       (["record_id", "pred", *[f"p_{c}" for c in CLASSES]], nb, "notebook predictions")]:
    miss = [c for c in need if c not in df.columns]
    if miss: sys.exit(f"{name} lacks columns {miss}")
j = nb.merge(app, on="record_id", how="left", suffixes=("_nb", "_app"), indicator=True)
absent = int((j["_merge"] == "left_only").sum())
j = j[j["_merge"] == "both"]
print(f"records in the notebook file: {len(nb)}; found in the app export: {len(j)}; missing from the app export: {absent}")
if j.empty: sys.exit("NOT EVALUATED: no common record_id")
cls_nb = j["pred"].map(dict(enumerate(CLASSES)))
diff_cls = j[cls_nb != j["predicted_condition"]]
dmax = max((j[f"p_{c}"] - j[f"model_score_{c}"]).abs().max() for c in CLASSES)
print(f"records with a DIFFERENT predicted class: {len(diff_cls)}")
print(f"largest absolute score difference: {dmax:.2e} (tolerance {tol:g})")
if len(diff_cls): print(diff_cls[["record_id", "predicted_condition", "pred"]].head(10).to_string(index=False))
ok = len(diff_cls) == 0 and dmax <= tol and absent == 0
print("RESULT:", "PASS (same classes, scores equal within tolerance)" if ok else ("PARTIAL/FAIL: see the differences above" if len(j) else "NOT EVALUATED"))
sys.exit(0 if ok else 1)
