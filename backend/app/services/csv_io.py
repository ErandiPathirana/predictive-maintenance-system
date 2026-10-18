"""Safe CSV upload handling.

Layers of defence, in order:
  1. file-level: extension, declared content type, size limit (read in chunks), binary signatures
  2. structure:  UTF-8 text, valid CSV, header exactly matches the model's contract
  3. content:    every cell checked (numbers, IDs, timestamps) and ALL problems reported together

The uploaded bytes are only ever parsed as text. They are never executed, unpickled or written to disk.
"""

import csv
import difflib
import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from fastapi import UploadFile

from app.core.errors import CsvValidationError, FileTooLargeError, UnsupportedFileError
from app.schemas import ID_PATTERN, MAX_YEAR, MIN_YEAR

ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "text/plain", "text/x-csv",
                         "application/vnd.ms-excel",   # what Windows browsers send for .csv
                         "application/octet-stream"}
BINARY_SIGNATURES = {b"PK\x03\x04": "a ZIP/Excel (.xlsx) file", b"MZ": "a Windows program", b"%PDF": "a PDF",
                     b"\xd0\xcf\x11\xe0": "a legacy Excel (.xls) file", b"\x7fELF": "a program"}
IGNORED_COLUMNS = ("condition_label",)       # tolerated in the notebook's clean copy, never used as an input
IDENTIFIER_COLUMNS = ("record_id", "motor_id")
OPTIONAL_COLUMNS = ("measured_at",)
MAX_ISSUES_REPORTED = 50
MAX_COLUMNS = 60
_ID_RE = re.compile(ID_PATTERN)
_NUM_RE = re.compile(r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$")   # plain ASCII decimal numbers only (no nan, inf, hex, underscores, non-Latin digits)


def safe_filename(name: str | None) -> str:
    base = (name or "upload.csv").replace("\\", "/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._ -]", "_", base)[:100] or "upload.csv"


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise UnsupportedFileError("Only .csv files are accepted. Save your spreadsheet as 'CSV UTF-8 (Comma delimited)'.")
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype and ctype not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedFileError(f"Unsupported content type '{ctype[:60]}'. Upload a plain CSV text file.")
    chunks, size = [], 0
    while chunk := await file.read(65536):
        size += len(chunk)
        if size > max_bytes:
            raise FileTooLargeError(f"The file is larger than the {max_bytes:,}-byte limit.")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw.strip():
        raise CsvValidationError("The file is empty.")
    for sig, label in BINARY_SIGNATURES.items():
        if raw.startswith(sig):
            raise UnsupportedFileError(f"This looks like {label}, not a CSV text file.")
    if b"\x00" in raw:
        raise UnsupportedFileError("The file contains binary data and is not a CSV text file.")
    return raw


@dataclass
class CsvAnalysis:
    issues: list[dict] = field(default_factory=list)
    issues_total: int = 0
    columns_found: list[str] = field(default_factory=list)
    ignored_columns: list[str] = field(default_factory=list)
    record_count: int = 0
    X: np.ndarray | None = None
    record_ids: list[str] = field(default_factory=list)
    motor_ids: list[str] = field(default_factory=list)
    measured_at: list[datetime | None] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.issues_total == 0 and self.X is not None

    def add(self, row: int | None, column: str | None, problem: str) -> None:
        self.issues_total += 1
        if len(self.issues) < MAX_ISSUES_REPORTED:
            self.issues.append({"row": row, "column": column, "problem": problem})


def _shorten(value: str, n: int = 24) -> str:
    return value if len(value) <= n else value[:n] + "..."


def _detect_timestamp_mode(value: str, fmt: str | None) -> str | None:
    try:
        datetime.fromisoformat(value)
        return "iso"
    except ValueError:
        pass
    if fmt:
        try:
            datetime.strptime(value, fmt)
            return "fmt"
        except ValueError:
            pass
    return None


def _parse_timestamp(value: str, mode: str, fmt: str | None) -> datetime:
    if mode == "iso":
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        dt = datetime.strptime(value, fmt)  # type: ignore[arg-type]
    if not MIN_YEAR <= dt.year <= MAX_YEAR:
        raise ValueError("year out of range")
    return dt


def analyse_csv(raw: bytes, bundle, max_rows: int) -> CsvAnalysis:
    res = CsvAnalysis()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        res.add(None, None, "The file is not UTF-8 text. In Excel choose 'CSV UTF-8 (Comma delimited)'.")
        return res

    header: list[str] | None = None
    rows: list[tuple[int, list[str]]] = []
    reader = csv.reader(io.StringIO(text))
    try:
        for cells in reader:
            if not any(c.strip() for c in cells):
                continue
            if header is None:
                header = [c.strip() for c in cells]
                continue
            rows.append((reader.line_num, cells))
            if len(rows) > max_rows:
                res.add(None, None, f"Too many records: the limit is {max_rows:,} per file.")
                return res
    except csv.Error as exc:
        res.add(None, None, f"The file is not valid CSV ({exc}).")
        return res
    if header is None:
        res.add(None, None, "The file has no header row.")
        return res
    res.columns_found = header
    res.record_count = len(rows)

    # ---------- header / contract checks ----------
    if any(h.startswith("Unnamed") or h in ("Record ID", "Measurement timestamps") for h in header):
        res.add(1, None, "This looks like the RAW master file with a two-row header. Upload the cleaned copy written by the notebook "
                         "(motor_clean_working_copy.csv) or the template from GET /api/template.csv.")
        return res
    if len(header) == 1 and ";" in header[0]:
        res.add(1, None, "The file looks semicolon-separated. Save it as comma-separated CSV.")
        return res
    if len(header) > MAX_COLUMNS:
        res.add(1, None, f"Too many columns ({len(header)}); the limit is {MAX_COLUMNS}.")
        return res
    dupes = sorted({h for h in header if header.count(h) > 1})
    for h in dupes:
        res.add(1, h, "Duplicate column name.")
    features = list(bundle.feature_names)
    allowed = set(features) | set(IDENTIFIER_COLUMNS) | set(OPTIONAL_COLUMNS) | set(IGNORED_COLUMNS)
    res.ignored_columns = [h for h in header if h in IGNORED_COLUMNS]
    for h in header:
        if h not in allowed:
            close = difflib.get_close_matches(h, sorted(allowed), n=1)
            res.add(1, _shorten(h, 40), "Unknown column." + (f" Did you mean '{close[0]}'?" if close else ""))
    for h in [*IDENTIFIER_COLUMNS, *features]:
        if h not in header:
            res.add(1, h, "Required column is missing.")
    if not rows:
        res.add(None, None, "The file has a header but no data rows.")
    if res.issues_total:
        return res

    # ---------- row checks (all problems collected, nothing predicted) ----------
    col = {name: i for i, name in enumerate(header)}
    fmt = (bundle.metadata.get("dataset") or {}).get("timestamp_format_assumed")
    ts_mode = None
    if "measured_at" in col:
        first = next((c[col["measured_at"]].strip() for _, c in rows if len(c) == len(header) and c[col["measured_at"]].strip()), None)
        if first is not None:
            ts_mode = _detect_timestamp_mode(first, fmt)
            if ts_mode is None:
                res.add(None, "measured_at", "Timestamp format not recognised. Use ISO 8601, e.g. 2025-04-01 07:20:00"
                        + (f" (or the training-data format {fmt})." if fmt else "."))
    X = np.zeros((len(rows), len(features)))
    seen_ids: set[str] = set()
    for r, (line, cells) in enumerate(rows):
        if len(cells) != len(header):
            res.add(line, None, f"Row has {len(cells)} values but the header has {len(header)}.")
            continue
        rid, mid = cells[col["record_id"]].strip(), cells[col["motor_id"]].strip()
        if not _ID_RE.match(rid):
            res.add(line, "record_id", "Must be 1-64 characters: letters, digits, '.', '_' or '-'.")
        elif rid in seen_ids:
            res.add(line, "record_id", "Duplicate record_id within the file.")
        seen_ids.add(rid)
        if not _ID_RE.match(mid):
            res.add(line, "motor_id", "Must be 1-64 characters: letters, digits, '.', '_' or '-'.")
        ts = None
        if "measured_at" in col and ts_mode:
            v = cells[col["measured_at"]].strip()
            if v:
                try:
                    ts = _parse_timestamp(v, ts_mode, fmt)
                except (ValueError, OverflowError):      # OverflowError: a timezone offset pushed the date outside the supported range
                    res.add(line, "measured_at", f"Invalid timestamp '{_shorten(v)}' (must use the same format on every row).")
        for j, name in enumerate(features):
            v = cells[col[name]].strip()
            if v == "":
                res.add(line, name, "Value is empty. Missing readings are not filled in.")
            elif not _NUM_RE.match(v):
                res.add(line, name, f"'{_shorten(v)}' is not a plain number.")
            else:
                x = float(v)
                if not math.isfinite(x):
                    res.add(line, name, "Number is too large.")
                else:
                    X[r, j] = x
        res.record_ids.append(rid); res.motor_ids.append(mid); res.measured_at.append(ts)
    if res.issues_total == 0:
        res.X = X
    return res


def parse_csv_or_raise(raw: bytes, bundle, max_rows: int) -> CsvAnalysis:
    analysis = analyse_csv(raw, bundle, max_rows)
    if not analysis.valid:
        raise CsvValidationError(
            "The file has problems. No predictions were made and nothing was saved.",
            {"issues_total": analysis.issues_total, "issues_shown": len(analysis.issues), "issues": analysis.issues})
    return analysis
