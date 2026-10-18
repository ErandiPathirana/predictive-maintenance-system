# Model evaluation assessment (ML researcher / academic evaluator view)

Scope: the motor-condition ANN only. Web-application correctness (see `docs/e2e-test-report.md`) and dissertation claims beyond the model are kept separate.
Status words: **EVIDENCED** = checked on your real artefacts here. **CODE-REVIEWED** = read in the notebook, but its result was not run here. **NOT EVALUATED** = no evidence available to me; the tool to produce it is listed in section 8.

## 1. What I actually had, and what I did not

| Item | Available to me? | Use |
|---|---|---|
| `motor_condition_ann_training.ipynb` (61 cells) | Yes, but **all 61 cells have no saved outputs** (never saved after running, or cleared) | read the code: split, scaling, tuning, evaluation, export |
| Dataset inspection report of `motor_predictive_maintenance_master.csv` (your run of `inspect_dataset.py`) | Yes | counts, ranges, missing values, duplicates, label distribution |
| The original dataset file | **No** | so no re-computation of any metric |
| The saved model bundle (`pm_condition_ann_v1.0.0`: weights, scaler, manifest) | **No** | so no re-prediction, no parity run |
| `predictions_20261017_110943.csv` (your web app's export of the real bundle `v1.0.0` on 1,938 records) | Yes | descriptive analysis only (section 5); it has **no true labels**, so it cannot give accuracy |
| Colab evaluation outputs (metrics, confusion matrix) | **No** | marked NOT EVALUATED |

Files named `audit_report` / `validation_report` that exist in my workspace were produced earlier from a **test fixture** (file `fx_clean.csv`, bundle "v-test"), not from your data. Their numbers are not used anywhere below.

## 2. Task-by-task result

| # | Task | Status | Finding |
|---|---|---|---|
| 1 | Target, classes, features, units, horizon | EVIDENCED / CODE-REVIEWED | Target `condition_label` with ordered classes Normal(0) / Alert(1) / Danger(2). 14 inputs in a fixed order: velocity (mm/s), gE and temperature (°C) at DE-H, DE-V, NDE-H, NDE-V, plus `rotational_speed_rpm` and `load_percent`. **There is no prediction horizon**: the model classifies the condition at the time of the reading. The notebook says this itself (section 1 and 18b). Position names "Header/Vrtex" are assumed to mean horizontal/vertical (unconfirmed in your own schema review). |
| 2 | Dataset quality | EVIDENCED (inspection report) | 1,938 records, 40 motors, unique Record IDs, 0 fully identical rows, no empty cells, one stray sub-heading row (handled by the loader). Labels: Normal 1,475 (76.1 %), Alert 347 (17.9 %), Danger 116 (6.0 %); imbalance Normal:Danger = 12.7:1. Timestamps month-first. Speed range 1,049–2,965 rpm and load 20–100 %: mixed machine types are possible. Suspicious labels, leakage and unit problems **were not re-checked here** (needs the file; audit notebook, section 8). |
| 3 | What the target represents | EVIDENCED | **Observed or assigned condition state, not a verified failure.** The file has no failure/repair/event column (notebook section 18b). Who or what assigned Normal/Alert/Danger is **undocumented** in the notebook (`LABEL_PROVENANCE.documented = False`, all TODO). Do not call these labels failure evidence. |
| 4 | Splits | CODE-REVIEWED | Motor-grouped 60/20/20 by number of motors (about 24/8/8), asserted disjoint; best of up to 5,000 random motor partitions chosen by **label counts only**, with at least 10 records of every class per split. Appropriate for "unseen motors". Weaknesses: only about 8 test motors; a single partition; Danger may sit in few motors; motor ID prefixes (the app export shows CIPR…, CIPS…) may mean machine families, which would act as a hidden predictor (not checked). A chronological split is not used, which is fine for condition classification but would be required for any future-failure claim. |
| 5 | Preprocessing fit on training only | CODE-REVIEWED | `StandardScaler().fit(X_train)` once; asserted `n_samples_seen_ == len(X_train)`; class weights from training labels only; no imputation (incomplete input is rejected). The same mean/scale are exported to `preprocessing.json`. The backend applies them (tested in the backend suite, 528 passed here, and in the end-to-end suite with a synthetic bundle). Not shown on your real bundle. |
| 6 | Independent test evaluation | **NOT EVALUATED** | The code evaluates once on the test motors (guarded against reuse) and computes accuracy, balanced accuracy, macro-F1, per-class P/R/F1, MCC, log-loss, a confusion matrix and motor-level bootstrap intervals. **No saved output exists**, so I cannot report a value. |
| 7 | Baselines | **NOT EVALUATED** (design reviewed) | Dummy, Logistic Regression and Random Forest are tuned on validation with declared grids and scored on the same test motors. Good design; no results available. |
| 8 | False positives / negatives | NOT EVALUATED (partly designed) | The notebook counts `danger_predicted_as_normal` and abnormal recall. Needs the run. Consequence statement is in section 6 below. |
| 9 | Artefacts load and reproduce inference | NOT EVALUATED on your bundle | The notebook asserts a NumPy-vs-Keras parity on **validation** rows (< 1e-5). The backend loader checks hashes, shapes and feature order (tested on test bundles only). Needs your real bundle (section 8, V10/V11 and E2E-B1). |
| 10 | Notebook vs deployed predictions on the same records | NOT EVALUATED | Script `compare_app_vs_notebook.py` added (section 8). Sanity-tested on synthetic files: it passes identical inputs and flags a flipped class and a missing record. |
| 11 | Limitations | EVIDENCED | See section 7. |
| 12 | Reproducible scripts | DONE | Section 8 and the files in `tools/`. |

## 3. Metrics table (measured values only)

| Metric (held-out test motors) | ANN | Random Forest | Logistic Regression | Dummy |
|---|---|---|---|---|
| Accuracy | not evaluated | not evaluated | not evaluated | not evaluated |
| Macro-F1 (95 % CI by motor) | not evaluated | not evaluated | not evaluated | not evaluated |
| Normal / Alert / Danger precision | not evaluated | not evaluated | not evaluated | not evaluated |
| Normal / Alert / Danger recall | not evaluated | not evaluated | not evaluated | not evaluated |
| Danger predicted as Normal (count) | not evaluated | not evaluated | not evaluated | not evaluated |

I will not fill these. Run section 8; the table is filled by `validation_outputs/validation_metrics.json`.

## 4. Dataset and leakage audit (summary)

| Check | Result |
|---|---|
| Duplicate / identical rows | EVIDENCED: 0 fully identical rows, 0 repeated Record IDs |
| Missing values | EVIDENCED: none in the 14 inputs or the label |
| Types | EVIDENCED: all inputs numeric after removing one stray sub-heading row |
| Class imbalance | EVIDENCED: 12.7 : 1 (Normal : Danger) |
| Identifier leakage (`record_id`, `motor_id`, timestamps as inputs) | CODE-REVIEWED: all excluded by an asserted `EXCLUDED` list |
| Row-level leakage between splits | CODE-REVIEWED: motor-grouped with disjointness assertion; the notebook also quantifies how much a random row split would inflate the score (section 11b); that output is not saved |
| Scaler leakage | CODE-REVIEWED: fitted on training motors only |
| Tuning leakage | CODE-REVIEWED: hyper-parameters chosen on validation macro-F1; the test set is used once. With about 8 validation motors and 24 random ANN trials the selection is noisy and mildly optimistic on validation (not on test) |
| Labels derived from the same sensors (label-rule leakage) | **NOT EVALUATED**: probe in section 12b exists, output not saved |
| Family / motor-type as hidden predictor | **NOT EVALUATED** (audit notebook P03/L04) |

## 5. What the real deployed model's predictions show (descriptive, NOT performance)

From `predictions_20261017_110943.csv` (1,938 rows, 40 motors, all `model_version v1.0.0`):

| Observation | Value |
|---|---|
| Predicted classes | Normal 1,487 · Alert 296 · Danger 155 |
| Labelled classes in the file | Normal 1,475 · Alert 347 · Danger 116 |
| Scores | each row sums to 1 within 1e-6; the stated class is the highest score in every row; no duplicate record IDs |
| Mean top score by predicted class | Normal 0.934 · Alert 0.751 · Danger 0.843 |
| Motors predicted as one class for (almost) all readings | e.g. CIPR05: all 50 readings Alert; CIPS03: all 48 Normal; CIPR08: 23 Alert and 25 Danger, no Normal |

Cautions: this file covers **all** motors, including those used for training and tuning, so agreement with labels here would not be an honest test result, and it does not include the labels anyway. The class counts being similar says nothing about per-record correctness. Whole motors predicted as a single class suggest motor-level effects (operating conditions or machine type); whether this matches the labels needs the validation run.

Provenance flag to resolve: every exported row carries `label_provenance_provisional = False` and `demonstration_only = False`. In the notebook that normally happens only when `LABEL_PROVENANCE["documented"]` was set to `True` (the bundle is otherwise stamped provisional); the flag could also have been edited by hand. I could not see which. The notebook contains no written evidence. If no data owner statement exists, this flag overstates what is known and the bundle should be re-exported as provisional.

## 6. Consequence of missed dangerous conditions

A `Danger` reading predicted as `Normal` (or `Alert`) is the costly error: the interface would show routine-monitoring advice for a motor the labels call dangerous. The notebook records this count; its value is not available to me. Given 116 Danger records, probably concentrated in a few motors, the test set contains few Danger records, so recall on `Danger` will be statistically uncertain and must be reported with its interval and its absolute count of misses. The web app already states that a prediction is not a confirmed fault and that scores are not calibrated probabilities.

## 7. Limitations (supported by the evidence above)

1. One dataset: 40 motors, one period (April–August 2025 per the export), few Danger records.
2. Labels of unknown origin; may reflect a rule applied to the same sensors; not verified failures.
3. No failure events and no horizon, so **no claim of predicting future failure** is supported (the notebook agrees).
4. Small number of test motors; one partition; intervals will be wide.
5. Class imbalance 12.7 : 1; accuracy alone is misleading.
6. No external validation (other sites, other motors, other time periods).
7. Scores are softmax outputs, not calibrated probabilities.

## 8. Defects and recommended fixes (found by review; none measured)

| ID | Severity | Finding | Fix |
|---|---|---|---|
| M1 | High | The training notebook has no saved outputs, so no reviewer can inspect the evaluation | Re-run top to bottom in Colab (`FAST_DEBUG = False`), save the notebook **with** outputs (clear any cells that print raw rows), and export `evaluation_report` with `ml/scripts/export_evaluation_report.py`; commit the metrics JSON, not the data |
| M2 | High | Exported rows say provenance is documented, but no evidence is in the notebook | Keep written evidence (who/what assigned the labels); otherwise set `documented=False` and re-export |
| M3 | Medium | Single motor partition, about 8 test motors | Report grouped cross-validation or several partitions (audit notebook P03 includes leave-one-family-out) and the bootstrap intervals |
| M4 | Medium | Possible family/machine-type shortcut (rpm 1,049–2,965; ID prefixes) | Run audit checks K05/L04 and the validator; discuss the result |
| M5 | Medium | Parity checked on validation rows only | Run validator V10/V11 on the test rows and the comparer below on the deployed app's output |
| M6 | Low | Validation-based selection among 24 ANN trials on about 8 motors is noisy | Report seed spread (the notebook stores it) |
| M7 | Low | Title and objective say "proactive failure prediction" | Word the research claim as condition classification, with future-failure prediction as future work, unless verified failure events are obtained |

## 9. How to produce the missing evidence (exact commands)

**A. Colab, data audit and independent model validation** (notebooks in `tools/`; they never modify your files)
1. Upload `pm_data_audit_colab.ipynb` to Colab, Runtime → Run all, upload the **original** `motor_predictive_maintenance_master.csv` when asked. Read the table top-down: FAIL must be fixed or explained, WARN are questions.
2. Open `pm_model_validation_colab.ipynb` in a **new** runtime. Provide the original CSV and the folder `pm_condition_ann_v1.0.0` (zip it if needed). Run all.
3. Download `validation_outputs.zip`. Files: `validation_report.md` (every check with PASS/FAIL/INFO), `validation_metrics.json` (fill section 3 from this), `confusion_matrix.png`, `precision_recall.png`, `per_motor_accuracy.png`, `test_errors.csv`, `test_predictions.csv` (private: contains IDs).

How to read it: the verdict line states Target A (condition) and Target B (future failure) separately. V04 = split reproduced and disjoint; V03a = scaler from training motors only; V06 = the saved model reproduces the notebook's recorded test result; V07 = metrics now computed with motor-level intervals; V09 = ANN against baselines on the same motors (the ANN is only worth reporting as better if its interval does not overlap a baseline's); V10/V11 = inference pipeline and NumPy-only reload; V13 = error analysis (adjacent-class errors versus Normal↔Danger errors). Treat any FAIL as a defect; INFO lines are findings, not passes.

**B. Compare the deployed app with the notebook on the same records** (task 10)
1. In the app, upload the original CSV (or only the test motors) and export History → CSV.
2. On your PC (PowerShell, in the project folder):
```powershell
python tools\compare_app_vs_notebook.py "C:\path\predictions_export.csv" "C:\path\validation_outputs\test_predictions.csv"
```
`PASS` means the same class for every record and scores equal within 5e-6 (the app prints 6 decimals). Any other result is a defect in preprocessing, feature order or the bundle.

**C. Real bundle in the backend and end-to-end tests**
```powershell
$env:PM_REAL_BUNDLE_DIR="C:\...\ml\artifacts\pm_condition_ann_v1.0.0"
python ml\scripts\validate_artifacts.py "$env:PM_REAL_BUNDLE_DIR"
cd tests\e2e_full; python -m pytest test_recommendation_rules.py -k "B1 or B2"
```

## 10. Conclusion

| Claim | Verdict |
|---|---|
| The ANN classifies the **recorded condition** (Normal / Alert / Danger) of **unseen motors** from one set of readings | **Not yet supported.** The design is sound (motor-grouped split, training-only scaling, baselines, one-shot test, intervals), but no measured result exists in what I could inspect. It becomes supported or not after section 9A; the Danger recall interval and the comparison with the baselines decide. |
| The deployed pipeline reproduces the notebook | **Not yet evaluated** on your real bundle (tools ready). |
| The model **predicts future failures** (proactive prediction) | **Not supported by this dataset**: no failure events, no horizon; `Danger` is a condition state. |
| The software pipeline works (validation, scoring, recommendations, storage, export) | Supported with a synthetic-trained model, separate document (`docs/e2e-test-report.md`). |
