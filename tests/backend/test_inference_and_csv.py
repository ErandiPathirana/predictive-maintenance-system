import numpy as np
import pytest

from app.services.csv_io import analyse_csv
from app.services.inference import forward
from conftest import csv_text


def test_forward_matches_independent_reference(loaded, truth):
    from conftest import reference_forward
    rng = np.random.default_rng(3)
    X = loaded.mean + rng.normal(size=(20, loaded.n_features)) * loaded.scale
    np.testing.assert_allclose(forward(loaded, X), reference_forward(truth["mean"], truth["scale"], truth["layers"], X), atol=1e-12)


def test_scores_sum_to_one_and_batch_equals_single(loaded):
    X = loaded.mean + np.arange(3).reshape(3, 1) * loaded.scale
    p = forward(loaded, X)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    np.testing.assert_allclose(p[1], forward(loaded, X[1:2])[0])


def A(loaded, text, max_rows=100):
    return analyse_csv(text.encode() if isinstance(text, str) else text, loaded, max_rows)


def problems(a):
    return " | ".join(i["problem"] for i in a.issues)


def test_valid_csv(loaded):
    a = A(loaded, csv_text(loaded, rows=3))
    assert a.valid and a.record_count == 3 and a.X.shape == (3, 14) and a.record_ids == ["REC001", "REC002", "REC003"]


def test_bom_and_ignored_label_column(loaded):
    a = A(loaded, b"\xef\xbb\xbf" + csv_text(loaded, extra_cols=("condition_label",)).encode())
    assert a.valid and a.ignored_columns == ["condition_label"]


def test_missing_columns_are_listed(loaded):
    a = A(loaded, csv_text(loaded, drop_cols=("de_h_ge", "load_percent")))
    assert not a.valid and a.X is None
    assert {i["column"] for i in a.issues} == {"de_h_ge", "load_percent"}


def test_unknown_column_gets_suggestion(loaded):
    t = csv_text(loaded, drop_cols=("de_h_ge",)).replace("de_h_temp_c", "de_h_tmp_c")
    a = A(loaded, t)
    assert "Did you mean 'de_h_temp_c'" in problems(a)


def test_non_numeric_cell_is_located(loaded):
    a = A(loaded, csv_text(loaded, mutate=lambda r, v: v.update(de_h_ge="abc") if r == 1 else None))
    assert not a.valid and a.issues[0]["row"] == 3 and a.issues[0]["column"] == "de_h_ge"


@pytest.mark.parametrize("bad", ["", "nan", "inf", "-inf", "1_000", "0x10", "1e999", "12,5", "NaN"])
def test_bad_numeric_values_rejected(loaded, bad):
    t = csv_text(loaded, mutate=lambda r, v: v.update(de_h_ge=f'"{bad}"') if r == 0 else None)
    assert not A(loaded, t).valid


def test_scientific_and_signed_numbers_accepted(loaded):
    t = csv_text(loaded, mutate=lambda r, v: v.update(de_h_ge="1.5e-2", de_h_temp_c="-3.2") if r == 0 else None)
    assert A(loaded, t).valid


def test_invalid_timestamp_reported(loaded):
    a = A(loaded, csv_text(loaded, rows=3, mutate=lambda r, v: v.update(measured_at="not a date") if r == 2 else None))
    assert not a.valid and a.issues[0]["column"] == "measured_at"


def test_training_data_timestamp_format_accepted(loaded):
    a = A(loaded, csv_text(loaded, mutate=lambda r, v: v.update(measured_at="4/1/2025 7:20")))
    assert a.valid and a.measured_at[0].month == 4 and a.measured_at[0].day == 1


def test_day_first_timestamp_is_not_guessed(loaded):
    a = A(loaded, csv_text(loaded, mutate=lambda r, v: v.update(measured_at="25/12/2025 07:20")))
    assert not a.valid and "not recognised" in problems(a)


def test_mixed_timestamp_formats_rejected(loaded):
    def mix(r, v): v.update(measured_at="2025-04-01 07:20:00" if r == 0 else "4/2/2025 7:20")
    assert not A(loaded, csv_text(loaded, mutate=mix)).valid


def test_timestamp_is_optional(loaded):
    a = A(loaded, csv_text(loaded, with_ts=False))
    assert a.valid and a.measured_at == [None, None]


def test_duplicate_record_id(loaded):
    a = A(loaded, csv_text(loaded, rows=2, ids=("SAME", "MOT{:02d}")))
    assert "Duplicate record_id" in problems(a)


@pytest.mark.parametrize("bad_id", ["bad id", "a;b", "x" * 65, "=cmd"])
def test_bad_ids_rejected(loaded, bad_id):
    assert not A(loaded, csv_text(loaded, mutate=lambda r, v: v.update(motor_id=f'"{bad_id}"') if r == 0 else None)).valid


def test_too_many_rows(loaded):
    a = A(loaded, csv_text(loaded, rows=6), max_rows=5)
    assert not a.valid and "Too many records" in problems(a)


def test_header_only_file(loaded):
    assert "no data rows" in problems(A(loaded, csv_text(loaded, rows=0)))


def test_raw_two_row_header_file_is_recognised(loaded):
    raw = "Record ID,Motor ID,Measurement timestamps,Drive end Header\n,,,DE_H_mm/s\nREC1,CIPR01,4/1/2025 7:20,0.88\n"
    assert "RAW master file" in problems(A(loaded, raw))


def test_semicolon_separated_hint(loaded):
    assert "semicolon" in problems(A(loaded, "record_id;motor_id;de_h_ge\nR1;M1;1\n"))


def test_ragged_row(loaded):
    t = csv_text(loaded, rows=2).rstrip("\r\n") + ",extra\r\n"
    assert "values but the header has" in problems(A(loaded, t))


def test_not_utf8(loaded):
    assert "UTF-8" in problems(A(loaded, b"record_id,motor_id\n\xff\xfe\x00\x00"))


def test_issue_list_is_capped_but_total_is_true(loaded):
    a = A(loaded, csv_text(loaded, rows=40, mutate=lambda r, v: v.update(de_h_ge="bad", de_h_temp_c="bad")))
    assert a.issues_total == 80 and len(a.issues) == 50
