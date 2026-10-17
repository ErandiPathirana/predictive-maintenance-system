# Recommendation rules

Code: `backend/app/services/recommendations.py` (ruleset `general-guidance-1.0`). Tests: `tests/backend/test_recommendations.py`.
The engine is separate from the ML model. It receives the model's predicted class **name** (never a class index) and gives advice. It never issues commands.

## What it does and does not use
| Input | Used? |
|---|---|
| Predicted class name (`Normal`, `Alert`, `Danger`, exact match) | Yes. The only thing that selects the rule set |
| Inputs flagged "outside the range seen in training" | Yes, as a **data-quality** hint: adds "check the flagged readings were measured and entered correctly". It is not an engineering limit |
| Sensor values compared with limits (for example "temperature too high") | **No.** No verified or approved engineering threshold exists in this project, so none is invented |
| Approved site procedures | Only if a site-guidance file is supplied (below). Otherwise none |
| Unknown class name | No recommendation is generated. The result says so. Nothing is guessed |

## Built-in general guidance
Every built-in action is labelled: *General guidance. Requires maintenance-engineer confirmation. No site-approved procedure is configured for this action.*

Each recommendation has: priority (1 = first), action, reason, suggested responsible role, timing category, optional safety note, source, and whether confirmation is required.
Timing categories (no exact deadlines are defined): *Immediate safety review*, *Prompt engineering assessment*, *Planned maintenance review*, *Routine monitoring*.

| Condition | Summary of the general guidance |
|---|---|
| Normal | Continue routine monitoring per the approved schedule; review historical trend; record the assessment; follow the preventive-maintenance plan. States that Normal is not a guarantee of health |
| Alert | Notify the responsible maintenance engineer; review current and historical readings; repeat or verify the measurement if appropriate; inspect per the approved inspection procedure (noise, heat, looseness, alignment, lubrication where relevant); change monitoring frequency only if an approved procedure allows. States that Alert is a prediction, not a confirmed diagnosis |
| Danger | Notify the responsible maintenance engineer **immediately** (always first); stop or isolate only through the site's approved shutdown, lockout/tagout and authorisation procedures; arrange a qualified inspection before return to service where procedures require; record readings, model output, timestamp and actions; check approved maintenance instructions before any repair. Safety notes: follow the site emergency procedure for an immediate hazard; do not open electrical equipment, remove guards or touch moving parts unless qualified and authorised |

What the rules never do: order a shutdown, name a mechanical fault, advise replacing parts, state an exact repair deadline, or promise a motor is healthy or safe. Tests enforce this wording.

## Optional site-approved guidance
A site can supply approved actions. The file is validated and refused **as a whole** if anything is missing. Required: `guidance_version`, `approved_by`, `approved_on` (YYYY-MM-DD), and per action: `action`, `reason`, `responsible_role`, `timing` (one of the four categories) and `procedure_ref`. `safety_note` is optional.
Site actions are added **after** the general guidance (they cannot remove or reorder the safety notifications), are labelled *Site-approved: <procedure_ref> (guidance version, approver, date)* and are not marked "requires confirmation".
Loading a file into the running API is added in a later stage. See `docs/site_guidance.example.json` for the format. **That example is made-up placeholder text, not an approved procedure. Never use it as real guidance.**

## Changing the rules
1. Edit the text in `recommendations.py`. 2. Increase `RULESET_VERSION`. 3. Update the tests and this page. 4. Ask the responsible maintenance engineer to review the wording.
Each stored assessment records the ruleset version it used.
