# Report e-mail and maintenance follow-up

Decision support only. The system never shuts down or controls equipment, and it never states that a motor is safe.

## What a user sees
1. **Result page** (New Assessment, or an assessment opened from History): Motor ID, reference (`PM-000123`), readings time, saved time, predicted condition (the model's own label), model scores (labelled as not calibrated probabilities), recommended steps, readings if available.
   * **Alert**: a warning saying prompt inspection by the responsible Plant Engineer is recommended.
   * **Danger**: "Attention: This motor has been classified as Danger by the assessment system. Contact the responsible Plant Engineer immediately for inspection and follow the site's approved safety procedures." plus the existing safety paragraph (not a shutdown order).
   * Both carry a text heading and a symbol, so they do not rely on colour.
2. **Email Assessment Report** (Alert/Danger only): type a recipient, optionally a note, review the summary, press **Send report**. The button is disabled while sending and after success. Success reads "accepted by the mail server" because SMTP acceptance is not proof of delivery.
3. **Maintenance follow-up** (Alert/Danger only): *Start maintenance follow-up* opens a case at **Pending Inspection**.

| From | To | Needs |
|---|---|---|
| Pending Inspection | Maintenance In Progress | nothing mandatory (engineer, start date, fault found are optional) |
| Maintenance In Progress | Repair Completed: Verification Required | actions performed |
| Repair Completed | Verified / Closed | outcome "Verified" and the name of the person who verified |
| Repair Completed | Maintenance In Progress | outcome "Not verified" and a comment |

Steps cannot be skipped. A closed case cannot be changed. Every change is appended to a log (`maintenance_updates`); earlier entries and the original assessment are never edited.

4. **Reassess Motor** (shown at Repair Completed): opens New Assessment with the Motor ID prefilled. The result is saved as a normal, separate assessment and linked to the case (same motor, later than the original, each assessment linkable once). Conditions are always compared; readings only when both assessments have them. **A Normal prediction does not close the case.**
5. **Assessment History**: filter *Maintenance status* (open / each status / no follow-up); columns *Maintenance status*, *Report e-mailed* (last time the mail server accepted a report) and "Reassessment of #N".

## Configuration (backend environment variables)
| Variable | Meaning |
|---|---|
| `SMTP_HOST`, `SMTP_FROM` | Both must be set to switch e-mail on. Otherwise the server answers 503 `email_not_configured` and the dialog says so |
| `SMTP_PORT` (587), `SMTP_SECURITY` (`starttls`, `ssl`, `none`) | `starttls` with 587 is typical; `ssl` with 465; `none` is for local testing |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Login, if the provider needs one. Gmail and Outlook usually need an **app password**, not the normal password |
| `EMAIL_ALLOWED_DOMAINS` | Comma-separated approved recipient domains |
| `EMAIL_MAX_PER_HOUR` (20) | Server-wide cap on accepted sends |
| `PUBLIC_APP_URL` | Adds `{url}/#/assessment/{id}` to the e-mail. Omitted if unset |

With `ENVIRONMENT=production` the server refuses to start with e-mail on unless `API_KEY` or `EMAIL_ALLOWED_DOMAINS` is set, so it cannot become an open mail relay. Secrets live only in environment variables (on Render: the Environment tab). They are never returned by the API, logged, or sent to the browser.

Apply the new tables with `python -m alembic upgrade head` (migration `0003`; it adds three tables and does not touch `predictions`). The Render start command already runs it.

## API
`GET /api/email-status`, `POST /api/assessments/{id}/email-report`, `GET /api/assessments/{id}/maintenance`, `POST /api/assessments/{id}/maintenance-case`, `POST /api/maintenance-cases/{id}/updates`, `POST /api/maintenance-cases/{id}/reassessments`, and a `maintenance_status` filter on `GET /api/predictions`. Details: `docs/api-schemas.md`.

## Limits you must know
* No user accounts. "Authorised user" means anyone with access (and the optional shared `API_KEY`). "Entered by" and "Verified by" are free text and are **not verified identities**.
* Raw readings are not stored by default (`STORE_INPUT_READINGS=false`). A fresh result can be e-mailed with readings (the browser sends them; the server re-scores them and refuses them unless they reproduce the saved result; they are not stored). A reopened old record has no readings, so its e-mail says so and the before/after comparison shows conditions only. Turning storage on changes a privacy default; decide that deliberately.
* "Accepted by the mail server" is not "read" or "delivered". Confirm important Danger cases by phone or radio.
* Recipient addresses are stored in `report_emails` (personal data). No PDF is attached; use *Print or save as PDF* on the result page.
* History survives restarts only with a persistent database (a SQLite file or PostgreSQL). Render Free's filesystem is erased on restart.
