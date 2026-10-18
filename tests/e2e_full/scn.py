"""Scenario registry: each end-to-end test declares its documentation (the 9 fields the report needs) next to its code."""
import json
from pathlib import Path

import pytest

REG: dict[str, dict] = {}


def scn(id, letter, title, *, pre, inp, exp, sev, fix, layer):
    """Decorator. `sev` / `fix` describe what a FAILURE of this test would mean (they are shown in the report only if the test fails or is blocked)."""
    def deco(fn):
        REG[id] = dict(id=id, letter=letter, title=title, preconditions=pre, input=inp, expected=exp, severity_if_fail=sev, corrective_action=fix, layer=layer)
        return pytest.mark.scn(id)(fn)
    return deco
