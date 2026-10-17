"""Writes docs/openapi.json and the schema reference table (docs/api-schemas.md) from the REAL application.
Run from backend/:  python scripts/generate_api_docs.py     (the model bundle is not needed)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"


def tname(s: dict) -> str:
    if "$ref" in s: return s["$ref"].split("/")[-1]
    if "anyOf" in s: return " or ".join(dict.fromkeys(tname(x) for x in s["anyOf"]))
    t = s.get("type")
    if t == "array": return f"list[{tname(s.get('items', {}))}]"
    if t == "object":
        ap = s.get("additionalProperties")
        return f"dict[str, {tname(ap)}]" if isinstance(ap, dict) and ap else "object"
    if s.get("format") in ("date-time", "date"): return s["format"]
    return t or "any"


def main() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite:///:memory:", auto_create_tables=True,
                              require_model_at_startup=False, _env_file=None))
    spec = app.openapi()
    (DOCS / "openapi.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    out = ["# API request and response schemas", "", "Generated from the running application (`backend/scripts/generate_api_docs.py`). "
           "Interactive version: `/docs`.", "", "## Endpoints", "", "| Method | Path | Summary |", "|---|---|---|"]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            out.append(f"| {method.upper()} | `{path}` | {op.get('summary', '')} |")
    out += ["", "## Schemas", ""]
    for name, sch in sorted(spec["components"]["schemas"].items()):
        if name in ("HTTPValidationError", "ValidationError"): continue
        out += [f"### {name}", ""]
        if sch.get("description"): out += [sch["description"], ""]
        out += ["| Field | Type | Required | Description |", "|---|---|---|---|"]
        req = set(sch.get("required", []))
        for f, p in sch.get("properties", {}).items():
            out.append(f"| `{f}` | {tname(p)} | {'yes' if f in req else 'no'} | {(p.get('description') or '').replace('|', '/')} |")
        out.append("")
    (DOCS / "api-schemas.md").write_text("\n".join(out), encoding="utf-8")
    print("wrote docs/openapi.json and docs/api-schemas.md")


if __name__ == "__main__":
    main()
