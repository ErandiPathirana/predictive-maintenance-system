"""The recommendation engine is tested WITHOUT the ML model, using controlled inputs."""
import json
import re

import pytest

from app.services import recommendations as rec
from app.services.recommendations import (ALERT, DANGER, NORMAL, SOURCE_GENERAL, SOURCE_SITE, SiteGuidanceError, load_site_guidance, parse_site_guidance,
                                          recommend)

FORBIDDEN = re.compile(r"\b(replace|replacement|swap|rebuild|overhaul|will fail|is failing|has failed|guarantee[sd]? (?:healthy|safe))\b", re.I)


@pytest.mark.parametrize("cond", [NORMAL, ALERT, DANGER])
def test_every_known_condition_gets_ordered_recommendations_with_all_fields(cond):
    r = recommend(cond)
    assert r.available and r.condition == cond and r.items
    assert [i.priority for i in r.items] == list(range(1, len(r.items) + 1))
    for i in r.items:
        assert i.action and i.reason and i.responsible_role and i.source_detail
        assert i.timing in rec.TIMING_ORDER
        assert i.source == SOURCE_GENERAL and i.requires_confirmation is True
        assert "confirmation" in i.source_detail.lower()


def test_normal_is_calm_and_never_promises_health():
    r = recommend(NORMAL)
    text = " ".join(i.action + " " + i.reason for i in r.items).lower()
    assert "routine monitoring" in text and "approved maintenance schedule" in text
    assert "not a guarantee" in text
    assert not r.urgent and all(i.timing in (rec.TIMING_ROUTINE, rec.TIMING_PLANNED) for i in r.items)


def test_alert_is_a_prediction_not_a_diagnosis_and_asks_for_engineer_and_inspection():
    r = recommend(ALERT)
    text = " ".join(i.action + " " + i.reason for i in r.items).lower()
    assert "not a confirmed fault diagnosis" in text
    assert "maintenance engineer" in r.items[0].action.lower()
    assert any("approved inspection procedure" in i.action for i in r.items)
    assert any("approved maintenance procedure" in i.action for i in r.items)   # monitoring change only per approved procedure
    assert not r.urgent


def test_danger_is_safety_first_and_never_orders_a_shutdown_or_repair():
    r = recommend(DANGER)
    assert r.urgent
    first = r.items[0]
    assert first.timing == rec.TIMING_IMMEDIATE and "immediately" in first.action.lower() and "maintenance engineer" in first.action.lower()
    text = " ".join(i.action + " " + i.reason + " " + (i.safety_note or "") for i in r.items)
    assert "lockout/tagout" in text and "authoris" in text
    assert "site's emergency" in text or "emergency procedure" in text
    assert "do not open electrical equipment" in text.lower()
    assert "qualified inspection" in text
    assert "record the sensor readings" in text.lower()
    assert "approved maintenance instructions" in text
    stop = [i for i in r.items if "stop or isolate" in i.action]
    assert stop and "approved shutdown" in stop[0].action          # stopping is conditional and goes through site procedures
    assert not re.search(r"^(stop|shut)\b", " ".join(i.action for i in r.items), re.I | re.M)


@pytest.mark.parametrize("cond", [NORMAL, ALERT, DANGER])
def test_no_forbidden_claims_in_any_text(cond):
    r = recommend(cond, ["de_h_ge"])
    for i in r.items:
        for t in (i.action, i.reason, i.safety_note or ""):
            assert not FORBIDDEN.search(t), t
    assert not FORBIDDEN.search(r.headline) and not FORBIDDEN.search(r.disclaimer)


def test_disclaimers_state_the_limits():
    r = recommend(DANGER)
    assert "not a safety-rated control system" in r.disclaimer and "does not issue shutdown commands" in r.disclaimer
    assert "No approved engineering thresholds" in r.threshold_note


def test_unknown_class_produces_no_recommendation_and_says_so():
    for bad in ("Critical", "danger", "", "2", "Normal "):
        r = recommend(bad)
        assert r.available is False and r.items == ()
        assert "No recommendation" in r.headline and "no recommendation" in r.summary.lower()
    assert recommend(None).available is False      # type: ignore[arg-type]


def test_class_index_is_never_used():
    assert recommend(2).available is False          # type: ignore[arg-type]  # an index is not a class name


def test_out_of_range_inputs_add_a_data_check_without_judging_values():
    r = recommend(ALERT, ["de_h_ge", "de_h_ge", "nde_v_temp_c"])
    check = [i for i in r.items if "measured and entered correctly" in i.action]
    assert len(check) == 1 and "de_h_ge" in check[0].reason and "nde_v_temp_c" in check[0].reason
    assert "less reliable" in check[0].reason
    assert recommend(ALERT).items != r.items and len(r.items) == len(recommend(ALERT).items) + 1


def test_for_danger_the_engineer_notification_stays_first_even_with_data_warnings():
    r = recommend(DANGER, ["de_h_ge"])
    assert "maintenance engineer immediately" in r.items[0].action
    assert "measured and entered correctly" in r.items[1].action


def test_summary_is_short_and_names_the_condition():
    for c in (NORMAL, ALERT, DANGER):
        s = recommend(c).summary
        assert s.startswith(c) and len(s) <= 500


# ---- site-approved guidance ----
GOOD = {
    "guidance_version": "SITE-2026-01", "approved_by": "J. Perera (Maintenance Manager)", "approved_on": "2026-03-01",
    "conditions": {"Alert": [{"action": "Complete form MI-12 within the shift.", "reason": "Site inspection routine.",
                              "responsible_role": "Responsible maintenance engineer", "timing": "Prompt engineering assessment",
                              "procedure_ref": "MP-014 rev 3", "safety_note": "Follow LOTO per MP-002."}]},
}


def test_site_actions_are_added_last_and_labelled_with_their_source():
    g = parse_site_guidance(GOOD)
    r = recommend(ALERT, (), g)
    site = [i for i in r.items if i.source == SOURCE_SITE]
    assert len(site) == 1 and r.items[-1] is site[0]
    assert "MP-014 rev 3" in site[0].source_detail and "J. Perera" in site[0].source_detail and "SITE-2026-01" in site[0].source_detail
    assert site[0].requires_confirmation is False and r.site_guidance_version == "SITE-2026-01"
    assert [i.priority for i in r.items] == list(range(1, len(r.items) + 1))
    assert all(i.source == SOURCE_GENERAL for i in r.items if i is not site[0])


def test_site_guidance_for_other_conditions_does_not_leak():
    g = parse_site_guidance(GOOD)
    assert recommend(NORMAL, (), g).site_guidance_version is None
    assert all(i.source == SOURCE_GENERAL for i in recommend(DANGER, (), g).items)


def test_site_guidance_cannot_remove_the_safety_notifications():
    r = recommend(DANGER, (), parse_site_guidance({**GOOD, "conditions": {"Danger": [{**GOOD["conditions"]["Alert"][0]}]}}))
    assert "maintenance engineer immediately" in r.items[0].action


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d.pop("approved_by"), "approved_by"),
    (lambda d: d.update(approved_on="01/03/2026"), "approved_on"),
    (lambda d: d.update(conditions={}), "conditions"),
    (lambda d: d["conditions"].update(Critical=[]), "Unknown condition"),
    (lambda d: d["conditions"]["Alert"][0].pop("procedure_ref"), "procedure_ref"),
    (lambda d: d["conditions"]["Alert"][0].update(timing="Next Tuesday"), "timing"),
    (lambda d: d["conditions"]["Alert"][0].update(action="  "), "action"),
    (lambda d: d["conditions"]["Alert"][0].update(safety_note=""), "safety_note"),
    (lambda d: d["conditions"].update(Alert=[]), "non-empty"),
])
def test_incomplete_site_guidance_is_refused(mutate, fragment):
    d = json.loads(json.dumps(GOOD))
    mutate(d)
    with pytest.raises(SiteGuidanceError, match=fragment):
        parse_site_guidance(d)


def test_load_site_guidance_file_errors(tmp_path):
    with pytest.raises(SiteGuidanceError, match="not found"):
        load_site_guidance(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(SiteGuidanceError, match="not valid JSON"):
        load_site_guidance(bad)
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(GOOD), encoding="utf-8")
    assert load_site_guidance(ok).guidance_version == "SITE-2026-01"


def test_result_is_serialisable_and_immutable():
    d = recommend(DANGER).to_dict()
    json.dumps(d)
    assert d["urgent"] is True and d["ruleset_version"] == rec.RULESET_VERSION
    with pytest.raises(Exception):
        recommend(DANGER).items[0].action = "x"          # type: ignore[misc]
