# Frontend manual test checklist (for a beginner)

Do this before a demo or hand-over. Takes about 30 minutes. Tick each box. Write the date and your browser at the top.
Test with a **test model** (made-up weights) first. Never treat a test model's answer as a real result.

Setup: start the backend (`python -m uvicorn app.main:app` in `backend`), start the frontend (`npm run dev` in `frontend`), open http://localhost:5173.

## A. First look
- [ ] The top right shows a coloured shape **and words** such as "Model ... ready" (not colour alone).
- [ ] Press **Tab** once: a box "Skip to main content" appears. Press **Enter**: the page stays and the content area gets focus. (It must NOT show "Page not found".)
- [ ] Each menu page changes the browser-tab title (Dashboard, New assessment, ...).

## B. New assessment (workflows 1-6)
- [ ] Open **New assessment**. There are 14 sensor boxes in 5 groups, each with a label and unit.
- [ ] Press **Analyse motor** with an empty form: a red list of 16 problems appears and the cursor/focus moves to it. Nothing is sent.
- [ ] Type `abc` in one reading, `1,5` in another, leave one empty: each box shows its own clear message in words.
- [ ] Type 250 as a temperature: an orange note says it is outside the usual range, but the form still accepts it.
- [ ] Click **Use now** next to the time: it fills with the current time.
- [ ] Fill every box (values 4 to 16 are fine for the test model), type a motor ID, press **Analyse motor**.
- [ ] Double-click the button very fast: only ONE record appears in History.
- [ ] Do the whole form again using **only the keyboard** (Tab, type, Enter). The box you are in always has a thick blue ring.

## C. Result and advice (workflow 9)
Run the test backend once for each class (`python tests/e2e/start_backend.py Normal`, then `Alert`, then `Danger`) and check:
- [ ] The result shows a word **and** a shape ("Danger" with a diamond), and the words "Predicted condition".
- [ ] **Normal:** routine monitoring advice, no red box.
- [ ] **Alert:** tells the person to inform the maintenance engineer and to arrange an inspection.
- [ ] **Danger:** a big dark-red box "Contact the responsible maintenance engineer now".
- [ ] Danger text says it is **not a confirmed fault and not a shutdown order**, and that stopping/isolating is done **only through approved site procedures** (lockout/tagout).
- [ ] No text anywhere tells an ordinary operator to open covers, repair, replace a part, or gives a deadline such as "within 2 hours" or a sensor limit such as "above 7 mm/s".
- [ ] The sentence "A predicted condition is a statistical estimate. It is not a confirmed machine failure" is visible.

## D. CSV upload (workflows 7-8)
- [ ] **Download CSV template**: the file opens in Excel and has the same column names as the model needs.
- [ ] Choose a good CSV: a 5-row preview appears, **Check file** says "File check passed", **Analyse file** gives a results link.
- [ ] Try these bad files, one at a time. For each, a message must say *which row and column* or *what is wrong*, and **Analyse file** must stay disabled: a column deleted, a letter in a number box, a blank number, the word `NaN`, a wrong date, an empty file, a `.txt` file, a row with extra commas.

## E. History, filters, export, trends (workflows 10-12)
- [ ] **Assessment history** lists saved results, newest first. Click an ID: the full result opens.
- [ ] Filter by motor ID: only that motor remains. Type a nonsense ID: "No stored predictions match these filters". **Clear** restores the list.
- [ ] Set From later than To: the page explains the mistake and Apply is disabled.
- [ ] **Export matching rows (CSV)** downloads a file that opens in Excel and only contains the filtered rows.
- [ ] After loading a CSV on Upload, **Motor monitoring** shows charts for a chosen motor, with a table alternative.
- [ ] (Known) There is no "model evaluation metrics" page: it was removed on purpose.

## F. Failures (workflow 13)
- [ ] Stop the backend, reload the page: the header says "Backend unreachable"; New assessment shows ONE red box with **Try again**; no technical words like "TypeError".
- [ ] Start the backend again, press **Try again**: the form appears.
- [ ] Fill the form, stop the backend, press Analyse: a message says the assessment was not completed and nothing was saved; your entries are still there.
- [ ] Start a backend without a model (`python tests/e2e/start_backend.py none`): the header says "no model"; Analyse is not offered.

## G. Screen sizes and accessibility (workflow 14)
- [ ] Browser zoom to 200%: nothing is cut off, no sideways scrolling of the whole page.
- [ ] Make the window phone-narrow (375 px, or Chrome DevTools device mode): a menu button appears; choosing a page closes the menu; the Danger result is fully readable, including the "Who: ..." labels.
- [ ] Tablet width (768 px): same checks.
- [ ] Print preview of a result: menus are hidden, the Danger box stays visible.
- [ ] Optional: install the **axe DevTools** or use Chrome **Lighthouse > Accessibility** on each page; expect no contrast errors.

## H. Real devices (not covered by the automated tests)
- [ ] Open the site on a real phone and tablet. Fill and submit a form with your finger. Rotate the screen.
- [ ] Try Firefox, Safari and Edge, and a screen reader (NVDA on Windows).
