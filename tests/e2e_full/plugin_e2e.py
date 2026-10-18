import json
import shutil
import sys
import time
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "backend"), str(HERE.parents[1] / "tests" / "backend")]   # tests/backend gives us its conftest.py as a plain module

from harness import OUT, Server  # noqa: E402
import scn as scn_mod  # noqa: E402

RESULTS: dict[str, dict] = {}


class Recorder:
    def __init__(self): self.actual = []; self.evidence = []
    def actual_(self, text): self.actual.append(str(text))
    def evidence_(self, text): self.evidence.append(str(text))


@pytest.fixture
def rec(request):
    r = Recorder(); request.node._rec = r; return r


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    m = item.get_closest_marker("scn")
    if not m:
        return
    sid = m.args[0]; entry = RESULTS.setdefault(sid, {"id": sid, "status": "PASS", "actual": [], "evidence": [], "failure": "", "nodes": []})
    if item.nodeid not in entry["nodes"]:
        entry["nodes"].append(item.nodeid)
    r = getattr(item, "_rec", None)
    if rep.when == "call" and r:
        entry["actual"] += r.actual; entry["evidence"] += r.evidence
    if rep.failed:
        entry["status"] = "FAIL"; entry["failure"] = (str(call.excinfo.value)[:600] if call.excinfo else "setup/teardown error")
    elif rep.skipped and hasattr(rep, "wasxfail"):
        entry["status"] = "KNOWN GAP"; entry["failure"] = rep.wasxfail
    elif rep.skipped and entry["status"] != "FAIL":
        reason = str(rep.longrepr[-1]) if isinstance(rep.longrepr, tuple) else str(rep.longrepr)
        entry["status"] = "BLOCKED" if "BLOCKED" in reason else "SKIPPED"; entry["failure"] = reason.replace("Skipped: ", "")[:400]


def pytest_sessionfinish(session, exitstatus):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results_api.json").write_text(json.dumps({"results": list(RESULTS.values()), "meta": scn_mod.REG}, indent=2))


# --------------------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def bundle_dir():
    d = OUT / "bundle"
    from synthetic_model import main as build
    shutil.rmtree(d, ignore_errors=True)
    build(d)
    return d


@pytest.fixture(scope="session")
def samples(bundle_dir):
    return json.loads((OUT / "samples.json").read_text())


@pytest.fixture(scope="session")
def srv(bundle_dir):
    db = OUT / "e2e_main.db"
    db.unlink(missing_ok=True)
    s = Server(bundle_dir, db, port=8101)
    s.start()
    assert not s.exited(), s.log_tail()
    yield s
    s.stop()


@pytest.fixture()
def api(srv):
    with httpx.Client(base_url=srv.url, timeout=20) as c:
        yield c


_counter = [0]


def unique(prefix="E2E"):
    _counter[0] += 1
    return f"{prefix}-{int(time.time()) % 100000}-{_counter[0]}"
