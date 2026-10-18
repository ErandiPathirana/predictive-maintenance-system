| ID | Scenario | Viewport | Test | Result | Note |
|---|---|---|---|---|---|
| E05-ALE | Alert | desktop | Submit valid readings → backend returns Alert; banner shows word + shape + 'Predicted condition' | **PASS** |  |
| E09-ALE | Alert | desktop | Alert: corrective-action guidance matches the rules and stays inside the safety limits | **PASS** | 5 recommendation cards |
| A11Y-result-Alert | Alert | desktop | axe-core (WCAG 2.2 A/AA) on the Alert result page | **PASS** |  |
| E05-DAN | Danger | desktop | Submit valid readings → backend returns Danger; banner shows word + shape + 'Predicted condition' | **PASS** |  |
| E09-DAN | Danger | desktop | Danger: corrective-action guidance matches the rules and stays inside the safety limits | **PASS** | 5 recommendation cards |
| A11Y-result-Danger | Danger | desktop | axe-core (WCAG 2.2 A/AA) on the Danger result page | **PASS** |  |
| E01 | Danger | desktop | Open the assessment form: title, nav, required fields, labels, skip link | **PASS** |  |
| E02 | Danger | desktop | Motor ID: type a new ID, save, then it is offered as a suggestion next time | **PASS** |  |
| E03 | Danger | desktop | Measurement time: 'Use now' fills it; future time warns; empty time is an error | **PASS** |  |
| E06 | Danger | desktop | Validation: errors are listed, focus moves to the summary, entries are kept, fixing fields allows submit | **PASS** | messages: Enter a number such as 4.2 (digits only, no units or letters). / Use a dot for decimals, for example 2.5. / That number is too large. / Enter a value. |
| E06c | Danger | desktop | Out-of-training-range value warns but is accepted (not silently blocked) | **PASS** |  |
| E06d | Danger | desktop | Keyboard only: Tab through every control, type values, press Enter to submit | **PASS** |  |
| E06e | Danger | desktop | Clear form: needs confirmation, Escape cancels and returns focus, confirm clears | **PASS** |  |
| E06f | Danger | desktop | Server rejects the request (422) → plain message shown, entries kept, no result shown | **PASS** |  |
| E13d | Danger | desktop | Server error (500): says nothing was saved, keeps entries, retry works | **PASS** |  |
| E17 | Danger | desktop | Double-click on 'Analyse motor' stores exactly one record | **PASS** |  |
| E07a | Danger | desktop | Valid CSV: 5-row preview appears, Check file passes, Analyse returns a result per record | **PASS** |  |
| E08-missing_column | Danger | desktop | Malformed CSV (missing_column) is rejected with a reason the user can understand | **PASS** | 1 required column is missing  de_h_ge  Column names must match exactly. Download the template and copy your values into it. |
| E08-text_value | Danger | desktop | Malformed CSV (text_value) is rejected with a reason the user can understand | **PASS** | File check found 1 problem Nothing was stored. Fix the items below in your file and choose it again. Problems found File row	Column	Problem 2	de_h_ge	'abc' is n |
| E08-empty_value | Danger | desktop | Malformed CSV (empty_value) is rejected with a reason the user can understand | **PASS** | File check found 1 problem Nothing was stored. Fix the items below in your file and choose it again. Problems found File row	Column	Problem 2	de_h_ge	Value is e |
| E08-bad_date | Danger | desktop | Malformed CSV (bad_date) is rejected with a reason the user can understand | **PASS** | File check found 1 problem Nothing was stored. Fix the items below in your file and choose it again. Problems found File row	Column	Problem All	measured_at	Time |
| E08-header_only | Danger | desktop | Malformed CSV (header_only) is rejected with a reason the user can understand | **PASS** | This file cannot be used The file has no data rows. Check that the first row contains column names. |
| E08-empty_file | Danger | desktop | Malformed CSV (empty_file) is rejected with a reason the user can understand | **PASS** | This file cannot be used The file is empty. |
| E08-not_csv | Danger | desktop | Malformed CSV (not_csv) is rejected with a reason the user can understand | **PASS** | This file cannot be used Please choose a .csv file. |
| E08-binary | Danger | desktop | Malformed CSV (binary) is rejected with a reason the user can understand | **PASS** | This file cannot be used The file has no data rows. Check that the first row contains column names. |
| E08-nan_inf | Danger | desktop | Malformed CSV (nan_inf) is rejected with a reason the user can understand | **PASS** | File check found 2 problems Nothing was stored. Fix the items below in your file and choose it again. Problems found File row	Column	Problem 2	de_h_ge	'NaN' is  |
| E08-too_many_columns | Danger | desktop | Malformed CSV (too_many_columns) is rejected with a reason the user can understand | **PASS** | File check found 1 problem Nothing was stored. Fix the items below in your file and choose it again. Problems found File row	Column	Problem 2	Whole file	Row has |
| E08x | Danger | desktop | Upload page: removing a file asks for confirmation | **PASS** |  |
| E07t | Danger | desktop | Download CSV template works and matches the model's columns | **PASS** | motor_upload_template.csv |
| E10 | Danger | desktop | Prediction history lists saved records (newest first) and links to the detail page | **PASS** |  |
| E11a | Danger | desktop | History filters: motor ID, condition, no-match empty state, clear | **PASS** | Model vQA.1 ready / 8 matching predictions. Showing 1 to 8. |
| E11b | Danger | desktop | History export: file downloads, header + rows, filter respected, safe against spreadsheet formulas | **PASS** | 6 rows, file predictions_20261018_050714.csv |
| E11c | Danger | desktop | Date filter: 'From' later than 'To' is explained and blocks the filter | **PASS** |  |
| E12a | Danger | desktop | Monitoring: before any file is loaded, the page explains what to do (no empty charts) | **PASS** |  |
| E12b | Danger | desktop | Monitoring: after loading a CSV, trend charts render for a chosen motor, with a table alternative | **PASS** | 3 chart svg elements |
| E12c | Danger | desktop | Dashboard: shows motors/conditions from history and sensor summary after a file load | **PASS** |  |
| E12d | Danger | desktop | Evaluation metrics: is there any screen that shows model evaluation metrics? | **N/A** | No evaluation-metrics screen exists. docs/frontend.md (line 83) says the Model evaluation page was removed on purpose; nothing to test. Metrics can still be exp |
| K01 | Danger | desktop | Skip link moves focus to the main content and keeps the page | **PASS** |  |
| K02 | Danger | desktop | Every page: every control reachable by Tab has a visible focus indicator | **PASS** |  |
| K03 | Danger | desktop | Route change: keyboard/screen-reader user is told the page changed (focus or title moves) | **PASS** |  |
| K04 | Danger | mobile | Mobile menu: Escape/Burger closes it and focus returns to the menu button | **PASS** |  |
| K05 | Danger | desktop | Text size: page still works with browser zoom 200% (viewport 640 wide ≈ 1280 at 200%) | **PASS** |  |
| A11Y-desktop-dashboard | Danger | desktop | axe-core (WCAG 2.2 A/AA) on dashboard at desktop | **PASS** |  |
| A11Y-desktop-assess | Danger | desktop | axe-core (WCAG 2.2 A/AA) on assess at desktop | **PASS** |  |
| A11Y-desktop-upload | Danger | desktop | axe-core (WCAG 2.2 A/AA) on upload at desktop | **PASS** |  |
| A11Y-desktop-results | Danger | desktop | axe-core (WCAG 2.2 A/AA) on results at desktop | **PASS** |  |
| A11Y-desktop-history | Danger | desktop | axe-core (WCAG 2.2 A/AA) on history at desktop | **PASS** |  |
| A11Y-desktop-monitoring | Danger | desktop | axe-core (WCAG 2.2 A/AA) on monitoring at desktop | **PASS** |  |
| A11Y-mobile-dashboard | Danger | mobile | axe-core (WCAG 2.2 A/AA) on dashboard at mobile | **PASS** |  |
| A11Y-mobile-assess | Danger | mobile | axe-core (WCAG 2.2 A/AA) on assess at mobile | **PASS** |  |
| A11Y-mobile-upload | Danger | mobile | axe-core (WCAG 2.2 A/AA) on upload at mobile | **PASS** |  |
| A11Y-mobile-results | Danger | mobile | axe-core (WCAG 2.2 A/AA) on results at mobile | **PASS** |  |
| A11Y-mobile-history | Danger | mobile | axe-core (WCAG 2.2 A/AA) on history at mobile | **PASS** |  |
| A11Y-mobile-monitoring | Danger | mobile | axe-core (WCAG 2.2 A/AA) on monitoring at mobile | **PASS** |  |
| A11Y-result | Danger | desktop | axe-core on the Danger result page, the error state and the validation-error state | **PASS** |  |
| E14-desktop-dashboard | Danger | desktop | Layout at desktop (1280px): dashboard has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-assess | Danger | desktop | Layout at desktop (1280px): assess has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-upload | Danger | desktop | Layout at desktop (1280px): upload has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-results | Danger | desktop | Layout at desktop (1280px): results has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-history | Danger | desktop | Layout at desktop (1280px): history has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-monitoring | Danger | desktop | Layout at desktop (1280px): monitoring has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-desktop-flow | Danger | desktop | Full assessment flow at desktop: fill form, submit, read Danger guidance, nothing clipped | **PASS** | all targets >= 24 px |
| E14-tablet-dashboard | Danger | tablet | Layout at tablet (768px): dashboard has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-assess | Danger | tablet | Layout at tablet (768px): assess has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-upload | Danger | tablet | Layout at tablet (768px): upload has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-results | Danger | tablet | Layout at tablet (768px): results has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-history | Danger | tablet | Layout at tablet (768px): history has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-monitoring | Danger | tablet | Layout at tablet (768px): monitoring has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-tablet-flow | Danger | tablet | Full assessment flow at tablet: fill form, submit, read Danger guidance, nothing clipped | **PASS** | all targets >= 24 px |
| E14-mobile-dashboard | Danger | mobile | Layout at mobile (375px): dashboard has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-assess | Danger | mobile | Layout at mobile (375px): assess has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-upload | Danger | mobile | Layout at mobile (375px): upload has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-results | Danger | mobile | Layout at mobile (375px): results has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-history | Danger | mobile | Layout at mobile (375px): history has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-monitoring | Danger | mobile | Layout at mobile (375px): monitoring has no sideways page scroll, header/nav usable | **PASS** |  |
| E14-mobile-flow | Danger | mobile | Full assessment flow at mobile: fill form, submit, read Danger guidance, nothing clipped | **PASS** | all targets >= 24 px |
| E13-nomodel-a | NoModel | desktop | Backend up but NO model loaded: header says so, New assessment is replaced by a clear explanation (no form, no fake result) | **PASS** | header: Backend up, no model |
| E13-nomodel-b | NoModel | desktop | No model: Upload page cannot analyse and says why | **PASS** |  |
| E13-nomodel-c | NoModel | desktop | No model: history of earlier saved records still opens (read-only) or fails with an understandable message | **PASS** |  |
| E05-NOR | Normal | desktop | Submit valid readings → backend returns Normal; banner shows word + shape + 'Predicted condition' | **PASS** |  |
| E09-NOR | Normal | desktop | Normal: corrective-action guidance matches the rules and stays inside the safety limits | **PASS** | 4 recommendation cards |
| A11Y-result-Normal | Normal | desktop | axe-core (WCAG 2.2 A/AA) on the Normal result page | **PASS** |  |
| E13-out-a | Outage | desktop | Backend OFF: header shows 'offline' with a shape and words, not only colour | **PASS** | Backend unreachable |
| E13-out-b | Outage | desktop | Backend OFF: New assessment explains the problem in plain words and offers Try again | **PASS** | New motor assessment The model could not be checked  Cannot reach the prediction server. Check that the backend is running and that you are online.  Check that  |
| E13-out-c | Outage | desktop | Backend OFF: History and Upload show an error state, not an endless spinner or blank page | **PASS** |  |
| E13-out-d | Outage | desktop | Backend dies while the user is on the filled form: Analyse gives a clear error, entries are kept, and work resumes when the backend returns | **PASS** |  |
| E13-slow-a | Slow | desktop | Slow backend (3 s): loading text appears, button is busy/disabled, a second click does not create a second record | **PASS** |  |
| E13-slow-b | Slow | desktop | Slow backend: History shows a loading message while waiting | **PASS** |  |
| E13-slow-c | Slow | desktop | Very slow backend (no answer within the 20 s limit): user gets a time-out message, can retry, entries are kept | **PASS** | The server took too long to answer. Try again in a moment. On free hosting the first request can take up |

Total 89: 88 PASS, 0 FAIL, 1 N/A
