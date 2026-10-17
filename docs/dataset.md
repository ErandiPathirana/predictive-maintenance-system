# Dataset description

> **Status: to be completed by the researcher.** No dataset has been selected or processed in this repository yet.
> Do not write any value below until you have verified it from the actual data source.

| Item | Your entry |
|---|---|
| Dataset name and version | TODO |
| Source and licence | TODO |
| Public or confidential? | TODO (if confidential, record who approved its use) |
| Collection period and sampling interval | TODO |
| Number of machines / assets | TODO |
| Number of records | TODO |
| Target variable and how "failure" is defined | TODO |
| Failure types included | TODO |
| Class balance (failure vs normal) | TODO (measure it; do not assume) |
| Missing values and how they are handled | TODO |

## Feature table

Fill in one row per model input. This table should match `ml/artifacts/feature_schema.json`.

| Feature | Meaning | Unit | Observed min | Observed max | Source of any range limit |
|---|---|---|---|---|---|
| TODO | | | | | Data / domain expert / none |

## Data handling rules for this project

- Raw data stays in Google Drive/Colab. It is never committed (see `.gitignore`).
- Document the train/validation/test split and justify it. For data recorded over time, a time-based split avoids leaking the future into training.
- Record any cleaning, filtering or resampling steps so the work is reproducible.
- Any range limit enforced by the API must be justified by the data or an expert, because the API rejects inputs outside it.
