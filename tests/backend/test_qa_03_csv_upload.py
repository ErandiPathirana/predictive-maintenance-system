"""QA areas 5, 6, 15: CSV validation, CSV batch prediction, malformed files, file-size and row-count limits.

Category: synthetic_bundle. Rejected uploads must be 4xx (never 5xx) and must leave the database empty (all-or-nothing).
"""

import io
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import FEATURES, csv_text, make_settings, upload


def total(client) -> int:
    return client.get("/api/predictions").json()["total"]


def header_line(loaded) -> str:
    return "record_id,motor_id,measured_at," + ",".join(loaded.feature_names)


def one_row(loaded, **cells) -> str:
    """Header + one valid row, with selected cells replaced (cells is {column: text})."""
    vals = {"record_id": "R1", "motor_id": "M1", "measured_at": "2025-04-01 07:20:00", **{n: f"{m:.3f}" for n, m in zip(loaded.feature_names, loaded.mean)}}
    vals.update(cells)
    cols = ["record_id", "motor_id", "measured_at", *loaded.feature_names]
    return ",".join(cols) + "\r\n" + ",".join(vals[c] for c in cols) + "\r\n"


# =============================== AREA 5: happy path and consistency ===============================
def test_a05_template_roundtrip(client, loaded):
    t = client.get("/api/template.csv")
    assert t.status_code == 200 and t.headers["content-type"].startswith("text/csv") and "attachment" in t.headers["content-disposition"]
    cols = t.text.strip().split(",")
    assert cols == ["record_id", "motor_id", "measured_at", *loaded.feature_names]
    row = {"record_id": "T1", "motor_id": "M9", "measured_at": "2025-05-01T10:00:00", **{n: str(m) for n, m in zip(loaded.feature_names, loaded.mean)}}
    r = upload(client, t.text.strip() + "\r\n" + ",".join(row[c] for c in cols) + "\r\n")
    assert r.status_code == 200 and r.json()["record_count"] == 1


def test_a05_batch_keeps_row_order_ids_and_counts(client, loaded):
    r = upload(client, csv_text(loaded, rows=6))
    j = r.json()
    assert r.status_code == 200 and j["record_count"] == 6
    assert [x["record_id"] for x in j["results"]] == [f"REC{i:03d}" for i in range(1, 7)]
    assert sum(j["class_counts"].values()) == 6 and set(j["class_counts"]) == {"Normal", "Alert", "Danger"}
    assert all(x["prediction_id"] for x in j["results"]) and len({x["prediction_id"] for x in j["results"]}) == 6


def test_a05_validate_endpoint_agrees_with_predict_and_stores_nothing(client, loaded):
    good, bad = csv_text(loaded, rows=3), csv_text(loaded, rows=3, mutate=lambda r, v: v.update(de_h_ge="abc") if r == 1 else None)
    assert upload(client, good, url="/api/uploads/validate").json()["valid"] is True
    v = upload(client, bad, url="/api/uploads/validate")
    assert v.status_code == 200 and v.json()["valid"] is False and v.json()["issues"][0]["row"] == 3     # line 3 = second data row
    assert upload(client, bad).status_code == 422
    assert total(client) == 0


def test_a05_extra_label_column_is_ignored_not_used(client, loaded):
    base = csv_text(loaded, rows=2, extra_cols=("condition_label",), mutate=lambda r, v: v.update(condition_label="Danger"))
    ctl = csv_text(loaded, rows=2, extra_cols=("condition_label",), mutate=lambda r, v: v.update(condition_label="Normal"))
    a, b = upload(client, base).json(), upload(client, ctl).json()
    assert [x["scores"] for x in a["results"]] == [x["scores"] for x in b["results"]], "condition_label must never influence a prediction"


def test_a05_utf8_bom_crlf_lf_and_quoted_fields(client, loaded):
    text = csv_text(loaded, rows=2)
    for variant in (text, text.replace("\r\n", "\n"), "﻿" + text, text.replace("REC001", '"REC001"')):
        assert upload(client, variant).status_code == 200


def test_a05_default_limits_are_consistent_with_each_other(bundle_dir, loaded):
    """With the shipped defaults (2 MB, 5,000 rows) a full-size file of realistic 6-decimal readings must fit in BOTH limits."""
    s = make_settings(bundle_dir)
    assert (s.max_upload_bytes, s.max_batch_rows) == (2_000_000, 5_000)
    rows = [header_line(loaded)]
    for i in range(s.max_batch_rows):
        rows.append(f"REC{i:05d},CIPR-{i % 8 + 1:02d},2025-04-01 07:20:00," + ",".join(f"{m + (i % 97) * 0.123457:.6f}" for m in loaded.mean))
    body = "\r\n".join(rows) + "\r\n"
    assert len(body.encode()) < s.max_upload_bytes, f"{len(body):,} bytes: the row limit cannot be reached under the size limit"
    with TestClient(create_app(s)) as c:
        t0 = time.perf_counter()
        r = upload(c, body)
        elapsed = time.perf_counter() - t0
        assert r.status_code == 200 and r.json()["record_count"] == 5_000
        assert total(c) == 5_000
        assert elapsed < 30, f"5,000-row batch took {elapsed:.1f}s"


# =============================== AREA 15: limits ===============================
def test_a15_file_size_limit_boundary_is_exact(bundle_dir, loaded):
    text = csv_text(loaded, rows=3)
    n = len(text.encode())
    with TestClient(create_app(make_settings(bundle_dir, max_upload_bytes=n))) as c:
        assert upload(c, text).status_code == 200                                   # exactly at the limit
    with TestClient(create_app(make_settings(bundle_dir, max_upload_bytes=n - 1))) as c:
        r = upload(c, text)
        assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
        assert total(c) == 0


def test_a15_row_limit_boundary_is_exact(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_batch_rows=4))) as c:
        assert upload(c, csv_text(loaded, rows=4)).status_code == 200
        r = upload(c, csv_text(loaded, rows=5))
        assert r.status_code == 422 and "Too many records" in r.text and total(c) == 4          # only the first (valid) upload was stored


def test_a15_limits_apply_to_the_dry_run_endpoint_too(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_batch_rows=2, max_upload_bytes=100))) as c:
        assert upload(c, csv_text(loaded, rows=2), url="/api/uploads/validate").status_code == 413
    with TestClient(create_app(make_settings(bundle_dir, max_batch_rows=2))) as c:
        r = upload(c, csv_text(loaded, rows=3), url="/api/uploads/validate")
        assert r.status_code == 200 and r.json()["valid"] is False


def test_a15_oversized_upload_is_cut_off_while_reading(bundle_dir):
    """A body far above the limit must be refused with 413 (not buffered into a prediction, not a 500)."""
    with TestClient(create_app(make_settings(bundle_dir, max_upload_bytes=10_000))) as c:
        r = c.post("/api/predict/batch", files={"file": ("big.csv", b"a,b\n" + b"1,2\n" * 2_000_000, "text/csv")})
        assert r.status_code == 413


def test_a15_issue_list_is_capped_even_for_a_hostile_file(client, loaded):
    r = upload(client, csv_text(loaded, rows=200, mutate=lambda i, v: v.update(de_h_ge="x")))
    d = r.json()["error"]["details"]
    assert r.status_code == 422 and d["issues_total"] == 200 and d["issues_shown"] == len(d["issues"]) <= 50


# =============================== AREA 6: malformed files ===============================
def test_a06_many_malformed_files_never_cause_a_server_error(client, loaded):
    good = csv_text(loaded, rows=2)
    files = {
        "empty": (b"", "a.csv"), "only whitespace": (b" \r\n\r\n ", "a.csv"), "header only": (header_line(loaded).encode() + b"\r\n", "a.csv"),
        "latin-1 bytes": (good.replace("REC001", "RÉC001").encode("latin-1"), "a.csv"),
        "utf-16": (good.encode("utf-16"), "a.csv"), "NUL byte": (good.encode() + b"\x00", "a.csv"),
        "zip/xlsx header": (b"PK\x03\x04" + b"0" * 200, "a.csv"), "pdf header": (b"%PDF-1.7 " + b"0" * 200, "a.csv"),
        "exe header": (b"MZ" + b"0" * 200, "a.csv"), "json inside .csv": (b'{"readings": {}}', "a.csv"), "html inside .csv": (b"<html><body>x</body></html>", "a.csv"),
        "single column": (b"record_id\r\nR1\r\n", "a.csv"), "semicolon": (good.replace(",", ";").encode(), "a.csv"),
        "tab separated": (good.replace(",", "\t").encode(), "a.csv"), "unbalanced quote": (good.replace("REC001", '"REC001').encode(), "a.csv"),
        "300 kB single field": (b"record_id,motor_id\r\n" + b"a" * 300_000 + b",x\r\n", "a.csv"),
        "duplicate header": ((good.replace("record_id", "record_id,record_id", 1)).encode(), "a.csv"),
        "ragged short row": (good.rstrip("\r\n").rsplit(",", 3)[0].encode(), "a.csv"),
        "many columns": (("c" + ",c".join(str(i) for i in range(500)) + "\r\n1\r\n").encode(), "a.csv"),
    }
    for label, (raw, name) in files.items():
        r = upload(client, raw, name=name)
        assert 400 <= r.status_code < 500, (label, r.status_code, r.text[:200])
        assert r.json()["error"]["code"], label
        assert "Traceback" not in r.text, label
    assert total(client) == 0


@pytest.mark.parametrize("name,ctype", [("data.txt", "text/plain"), ("data", "text/csv"), ("data.csv.exe", "text/csv"), ("data.xlsx", "text/csv"),
                                        ("data.csv", "application/zip"), ("data.csv", "image/png"), ("data.csv", "application/pdf")])
def test_a06_wrong_file_type_is_415(client, loaded, name, ctype):
    r = upload(client, csv_text(loaded), name=name, ctype=ctype)
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file"


def test_a06_wrong_multipart_field_or_method(client, loaded):
    assert client.post("/api/predict/batch", files={"document": ("a.csv", csv_text(loaded).encode(), "text/csv")}).status_code == 422
    assert client.post("/api/predict/batch").status_code == 422
    assert client.post("/api/predict/batch", json={"file": "x"}).status_code == 422
    assert client.get("/api/predict/batch").status_code == 405


@pytest.mark.parametrize("bad", ["NaN", "nan", "inf", "-inf", "Infinity", "", "1,5", "1 000", "0x10", "1_000", "1e999", "--1", "1.2.3", "٣٤.٥", "１２", "TRUE", "12abc", "=1+1", "'1"],
                         ids=lambda b: repr(b))
def test_a06_bad_numeric_cells_are_located_and_rejected(client, loaded, bad):
    r = upload(client, one_row(loaded, de_h_ge=f'"{bad}"' if "," in bad else bad))
    assert r.status_code == 422, f"{bad!r} was accepted"
    issue = r.json()["error"]["details"]["issues"][0]
    assert issue["column"] == "de_h_ge" and issue["row"] == 2
    assert total(client) == 0


@pytest.mark.parametrize("good", ["0", "-0", "+5", "5.", ".5", "1e3", "1E-3", "-12.5e+2", "0.000001", "123456789012"])
def test_a06_plain_numbers_are_accepted(client, loaded, good):
    assert upload(client, one_row(loaded, de_h_ge=good)).status_code == 200


@pytest.mark.parametrize("ts", ["garbage", "2025-02-30 10:00:00", "2025-13-01 00:00:00", "2025-04-01 25:00:00", "13/45/2025 10:00", "1900-01-01 00:00:00",
                                "2999-01-01 00:00:00", "0001-01-01T00:00:00", "9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00"])
def test_a06_invalid_or_implausible_csv_timestamps_are_rejected(client, loaded, ts):
    r = upload(client, one_row(loaded, measured_at=ts))
    assert r.status_code == 422 and r.json()["error"]["details"]["issues"][0]["column"] == "measured_at"


def test_a06_timestamp_column_is_optional_and_blank_cells_are_allowed(client, loaded):
    assert upload(client, csv_text(loaded, rows=2, with_ts=False)).status_code == 200
    assert upload(client, one_row(loaded, measured_at="")).status_code == 200


def test_a06_bad_ids_in_csv(client, loaded):
    for bad in ("has space", "../x", "x" * 65, "a;b", "=cmd", ""):
        r = upload(client, one_row(loaded, record_id=bad if "," not in bad else f'"{bad}"'))
        assert r.status_code == 422, bad
    assert upload(client, csv_text(loaded, rows=2, ids=("SAME", "M{:02d}"))).status_code == 422          # duplicate record_id inside one file


def test_a06_header_mistakes_get_helpful_messages(client, loaded):
    missing = upload(client, csv_text(loaded, drop_cols=("load_percent",)))
    assert "load_percent" in missing.text and "missing" in missing.text.lower()
    typo = upload(client, csv_text(loaded).replace("de_h_ge", "de_h_gE"))
    assert "Did you mean" in typo.text


def test_a06_columns_are_read_by_name_not_by_position(client, loaded):
    base = csv_text(loaded, rows=1)
    lines = base.splitlines()
    cols, vals = lines[0].split(","), lines[1].split(",")
    order = list(reversed(range(len(cols))))
    shuffled = "\r\n".join([",".join(cols[i] for i in order), ",".join(vals[i] for i in order)]) + "\r\n"
    a, b = upload(client, base).json()["results"][0], upload(client, shuffled).json()["results"][0]
    assert a["scores"] == b["scores"] and a["predicted_condition"] == b["predicted_condition"]
