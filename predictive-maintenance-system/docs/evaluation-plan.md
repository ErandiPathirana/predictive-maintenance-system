# Research artefact evaluation plan

> A plan, not results. Decide and justify each TODO with your supervisor before collecting data.

## Evaluation questions
1. **Model quality:** how well does the model predict failures on unseen data?
2. **Artefact quality:** does the prototype work reliably as software?
3. **Usefulness and usability:** can the intended users understand and use it?

## 1. Model evaluation
- Hold out a test set that is used **once**; choose models and thresholds on validation data only.
- For failure data, which is usually imbalanced, plain accuracy can mislead. Report metrics such as precision, recall, F1 and PR-AUC, plus a confusion matrix. Justify the choice. TODO
- Prevent leakage: for time-ordered data use a time-based split; keep records from one machine/run together where relevant. TODO
- Compare against at least one simple baseline (e.g. a majority-class or simple rule). TODO
- Discuss the real-world cost of missed failures versus false alarms, using evidence from the literature or a domain expert rather than invented numbers. TODO
- Optionally check probability calibration. TODO

## 2. Software evaluation
- Automated test results (backend and frontend) from `docs/testing-plan.md`.
- Response time of `/api/v1/predict` measured on the deployed system. State the method and the conditions. TODO
- Error-handling checks: invalid, missing and out-of-range inputs produce clear messages.

## 3. User evaluation (with the viva panel or volunteers)
- Short task-based session: check status, enter readings, interpret the result. TODO tasks
- Collect feedback with a standard instrument such as the System Usability Scale (SUS) plus open comments. TODO
- Obtain any ethics approval your university requires before involving participants. TODO
- Report sample size honestly; with few participants, results are indicative only.

## Threats to validity (write these up)
- Dataset may not represent your target factory conditions.
- Small or imbalanced data.
- Tuning choices made on limited validation data.
- Prototype tested on few users.

## Reporting rule
Every number in the dissertation must trace back to a script, notebook cell or test output you actually ran.
