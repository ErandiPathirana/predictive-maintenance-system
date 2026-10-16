# Model card

> **Status: template.** Complete this only from your own verified experiments. Do not copy numbers from papers or other projects as if they were yours.

## Model details
- Name / version: TODO (must match `model_metadata.json`)
- Algorithm and key hyperparameters: TODO
- Training date and environment (Python, scikit-learn versions): TODO
- Author: TODO

## Intended use
- Decision support for maintenance planning in a research prototype.
- **Not** intended as a safety system or as the only basis for stopping or running a machine.

## Training data
See `docs/dataset.md`. Split strategy and rationale: TODO.

## Evaluation (fill in only from the held-out test set, evaluated once)

| Metric | Value | Notes |
|---|---|---|
| Precision (failure class) | TODO | |
| Recall (failure class) | TODO | |
| F1 / PR-AUC / other chosen metric | TODO | Say why these metrics suit imbalanced failure data |
| Confusion matrix | TODO | |
| Decision threshold and how it was chosen | TODO | Chosen on validation data, never test data |

## Limitations (complete honestly)
- Data conditions the model was NOT trained on: TODO
- Known failure modes / weak spots: TODO
- Generalisation to other machines, plants or sensors: TODO
- Probability calibration status: TODO

## Ethical and operational considerations
- Cost of a missed failure versus a false alarm: TODO (domain-specific; discuss, do not assume)
- Human oversight: a qualified person must review predictions.
