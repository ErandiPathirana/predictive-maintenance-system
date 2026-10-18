# Model card: Motor condition classifier (ANN) v1.0.0

> **Label provenance documented (see model card).**
> Research prototype for a final-year project. Decision support only. Not a safety system.

## Model details
- Task: classify motor condition as Normal / Alert / Danger from 14 inputs (Option A).
- Architecture: MLP, 3 hidden layer(s) x 64 units (ReLU), dropout 0.1, L2 0.0001, softmax output; Adam lr 0.001; class weighting: balanced; best epoch 7.
- Created: 2026-10-17T02:12:12+00:00 | Seed: 42 | Frameworks: TensorFlow 2.21.0, Keras 3.13.2, scikit-learn 1.6.1.

## Intended use
- Exploring whether recorded motor condition can be classified from sensor readings for **unseen motors**, as a research artefact.
## Not intended for
- Safety decisions, replacing engineering inspection, or predicting **future failures** (no verified failure events were used).

## Data
- File `motor_predictive_maintenance_master.csv` (SHA-256 `0270fc74bc9f428b...`), 1938 records, 40 motors, 2025-04-01 to 2025-08-24.
- Class counts: Normal 1475, Alert 347, Danger 116.
- Inputs (in this order): de_h_velocity_mm_s, de_h_ge, de_h_temp_c, de_v_velocity_mm_s, de_v_ge, de_v_temp_c, nde_h_velocity_mm_s, nde_h_ge, nde_h_temp_c, nde_v_velocity_mm_s, nde_v_ge, nde_v_temp_c, rotational_speed_rpm, load_percent.
- Excluded on purpose: condition_label, record_id, motor_id, measured_at.

## Label provenance
| Question | Answer |
|---|---|
| Documented? | True |
| Assigned by | Maintenance engineer, by inspection |
| Rule or standard | Engineering standards |
| Assigned from the same sensor columns? | None |
| Evidence | TODO: email, document, or meeting date |

## Evaluation design
- Motor-grouped split: train 24 motors / 1164 records, validation 8 / 393, test 8 / 381.
- Standardisation fitted on training motors only. Tuning used validation data only. Test set evaluated once.

## Results
**Validation (used for tuning, optimistic):**

| model | accuracy | macro_F1 | balanced_acc | Alert_recall | Danger_recall |
|---|---|---|---|---|---|
| ANN (selected) | 0.878 | 0.798 | 0.764 | 0.386 | 0.917 |
| LogisticRegression (tuned) | 0.911 | 0.847 | 0.819 | 0.643 | 0.833 |
| RandomForest (tuned) | 0.880 | 0.783 | 0.723 | 0.471 | 0.708 |
| Dummy (most frequent) | 0.761 | 0.288 | 0.333 | 0.000 | 0.000 |

**Test (single evaluation, 381 records, 8 motors):**

| model | accuracy | balanced_acc | macro_F1 | weighted_F1 | Normal_recall | Alert_recall | Danger_recall |
|---|---|---|---|---|---|---|---|
| ANN | 0.898 | 0.839 | 0.755 | 0.900 | 0.972 | 0.544 | 1.000 |
| RandomForest | 0.950 | 0.927 | 0.912 | 0.952 | 0.955 | 0.956 | 0.870 |
| LogisticRegression | 0.945 | 0.927 | 0.872 | 0.947 | 0.972 | 0.809 | 1.000 |
| Dummy (most frequent) | 0.761 | 0.333 | 0.288 | 0.658 | 1.000 | 0.000 | 0.000 |

**Test uncertainty (95% bootstrap intervals, resampling motors):**

| model | macro_F1 | macro_F1 95% CI | Danger_recall | Danger_recall 95% CI |
|---|---|---|---|---|
| ANN | 0.755 | [0.587, 0.910] | 1.000 | [1.000, 1.000] |
| RandomForest | 0.912 | [0.740, 0.972] | 0.870 | [0.667, 1.000] |
| LogisticRegression | 0.872 | [0.718, 0.942] | 1.000 | [1.000, 1.000] |
| Dummy (most frequent) | 0.288 | [0.229, 0.320] | 0.000 | [0.000, 0.000] |

**ANN per-class test results:**

| class | precision | recall | f1 | support |
|---|---|---|---|---|
| Normal | 0.986 | 0.972 | 0.979 | 290.000 |
| Alert | 0.822 | 0.544 | 0.655 | 68.000 |
| Danger | 0.460 | 1.000 | 0.630 | 23.000 |

- Confusion matrix (rows actual, columns predicted; Normal, Alert, Danger): [[282, 8, 0], [4, 37, 27], [0, 0, 23]]
- Danger records predicted as Normal: 0
- Seed stability (validation macro-F1, mean +/- sd over 5 seeds): 0.726 +/- 0.051
- These numbers come from this run on this dataset. They do not demonstrate real-world failure-prediction ability.

## Assumptions (unconfirmed)
- 'Header' and 'Vrtex' (as typed in the file) are assumed to mean horizontal and vertical. Unconfirmed.
- The type of velocity behind 'mm/s' (RMS, peak, ...) is not specified in the file.
- The definition and measurement band of 'gE' are not specified in the file.
- Whether rotational speed and load are measured or nominal is unconfirmed.
- Timestamps are read month-first (%m/%d/%Y %H:%M); inferred from the data, not confirmed by the data owner.

## Limitations
- **Label provenance:** documented (see table). Metrics measure agreement with these labels, not with true machine health.
- **Not failure prediction:** the file has no verified failure-event timestamps; `Danger` is a condition state, not a failure.
- **Few motors:** the test set holds 8 motors. Scores are uncertain (see confidence intervals) and may change materially with another motor split.
- **Single dataset:** no evidence about other plants, motor types, sensors or mounting conditions.
- **Possible label-rule learning:** if labels were derived from sensor thresholds, the network may reproduce the rule (see Section 12b diagnostic).
- **No calibration or cost analysis:** probabilities were not calibrated and no real maintenance costs were available.
- **Single time-point input:** the model sees one reading, not the history of the motor.

## Loading
Use `reference_inference.py` (NumPy only): `bundle = load_bundle(dir)` then `predict(bundle, readings)`. The loader verifies `MANIFEST.json` checksums first.
