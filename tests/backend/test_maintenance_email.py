"""Report e-mail and maintenance follow-up.

No real e-mail is sent anywhere in these tests: smtplib.SMTP is replaced by a recording fake, so they prove OUR code's behaviour
(validation, duplicate guard, failure handling, what the message contains), not that a real mail server delivers.
"""
import smtplib
from datetime import date, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import make_settings

A = "/api/assessments"
SMTP_ENV = dict(smtp_host="smtp.test.invalid", smtp_from="alerts@test.invalid", smtp_username="user", smtp_password="s3cret-pass", api_key=None)


def body(readings, motor="MOT01", **kw):
    return {"motor_id": motor, "measured_at": "2025-04-01T07:20:00", "readings": readings, **kw}


def force(monkeypatch, k):
    def fake(bundle, X):
        out = np.full((len(X), 3), 0.05); out[:, k] = 0.9
        return out
    monkeypatch.setattr("app.api.routes_assessments.score_matrix", fake)
    monkeypatch.setattr("app.api.routes_maintenance.score_matrix", fake)


class FakeSMTP:
    sent, logins, fail, refuse = [], [], None, None

    def __init__(self, host, port, timeout=None, **kw):
        if FakeSMTP.fail == "connect":
            raise OSError("network down")

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, context=None): pass

    def login(self, u, p):
        if FakeSMTP.fail == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"bad")
        FakeSMTP.logins.append((u, p))

    def send_message(self, msg):
        if FakeSMTP.refuse:
            return {msg["To"]: (550, b"no")}
        FakeSMTP.sent.append(msg)
        return {}


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.logins, FakeSMTP.fail, FakeSMTP.refuse = [], [], None, None
    monkeypatch.setattr("app.services.report_email.smtplib.SMTP", FakeSMTP)


@pytest.fixture
def mail_client(bundle_dir):
    with TestClient(create_app(make_settings(bundle_dir, public_app_url="https://app.test.invalid", **SMTP_ENV))) as c:
        yield c


def make(c, readings, monkeypatch, k=2, **kw):
    force(monkeypatch, k)
    r = c.post(A, json=body(readings, **kw))
    assert r.status_code == 201, r.text
    return r.json()


def body_text(msg):
    return msg.get_body(("plain",)).get_content()


# ---------- e-mail ----------
def test_status_endpoint_never_exposes_credentials(mail_client, client):
    s = mail_client.get("/api/email-status").json()
    assert s["configured"] is True and s["link_in_report"] is True and "s3cret" not in str(s)
    assert client.get("/api/email-status").json()["configured"] is False


def test_successful_send_contains_required_content_and_is_logged(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch, k=2)
    r = mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test", "note": "Please check", "readings": readings})
    assert r.status_code == 200 and r.json()["sent"] is True and r.json()["readings_included"] is True
    assert "does not guarantee" in r.json()["message"]
    m = FakeSMTP.sent[0]
    t = body_text(m)
    assert m["To"] == "eng@plant.test" and "Danger" in m["Subject"] and f"PM-{a['assessment_id']:06d}" in m["Subject"]
    for needle in ("MOT01", "Danger", "de_h_temp_c", "not calibrated probabilities", "Recommended next action", "Please check",
                   f"https://app.test.invalid/#/assessment/{a['assessment_id']}", "qualified engineer"):
        assert needle in t, needle
    assert FakeSMTP.logins == [("user", "s3cret-pass")]
    detail = mail_client.get(f"{A}/{a['assessment_id']}/maintenance").json()
    assert [e["status"] for e in detail["emails"]] == ["sent"] and detail["emails"][0]["recipient"] == "eng@plant.test"
    hist = mail_client.get("/api/predictions").json()["items"][0]
    assert hist["report_sent_at"] is not None


def test_no_link_without_public_url_and_no_readings_when_not_supplied(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir, **SMTP_ENV))) as c:
        a = make(c, readings, monkeypatch, k=1)
        assert c.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"}).json()["readings_included"] is False
        t = body_text(FakeSMTP.sent[0])
        assert "/#/assessment/" not in t and "Not included" in t


@pytest.mark.parametrize("bad", ["", "no-at-sign", "a@b", "a b@c.com", "a@@c.com", "x@y.com\nBcc: z@z.com", "a@c.com, b@c.com", "<a@c.com>", "a" * 250 + "@c.com"])
def test_invalid_addresses_are_rejected_and_nothing_is_sent(mail_client, readings, monkeypatch, bad):
    a = make(mail_client, readings, monkeypatch)
    r = mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": bad})
    assert r.status_code == 422 and not FakeSMTP.sent


def test_normal_assessment_cannot_be_e_mailed(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch, k=0)
    assert mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"}).status_code == 422 and not FakeSMTP.sent


def test_not_configured_returns_503_and_sends_nothing(client, readings, monkeypatch):
    a = make(client, readings, monkeypatch)
    r = client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "email_not_configured" and not FakeSMTP.sent


@pytest.mark.parametrize("mode,code", [("connect", "email_failed"), ("auth", "email_failed")])
def test_smtp_failures_are_reported_as_failures_and_logged_failed(mail_client, readings, monkeypatch, mode, code, caplog):
    a = make(mail_client, readings, monkeypatch)
    FakeSMTP.fail = mode
    r = mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"})
    assert r.status_code == 502 and r.json()["error"]["code"] == code
    assert "s3cret" not in r.text and "s3cret" not in caplog.text
    d = mail_client.get(f"{A}/{a['assessment_id']}/maintenance").json()
    assert [e["status"] for e in d["emails"]] == ["failed"]
    assert mail_client.get("/api/predictions").json()["items"][0]["report_sent_at"] is None      # a failure never counts as sent


def test_recipient_refused_by_server_is_a_failure(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch)
    FakeSMTP.refuse = True
    assert mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"}).status_code == 502


def test_duplicate_send_is_blocked_but_failed_attempt_can_be_retried(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch)
    url = f"{A}/{a['assessment_id']}/email-report"
    FakeSMTP.fail = "connect"
    assert mail_client.post(url, json={"recipient": "eng@plant.test"}).status_code == 502
    FakeSMTP.fail = None
    assert mail_client.post(url, json={"recipient": "eng@plant.test"}).status_code == 200      # retry after failure is allowed
    r = mail_client.post(url, json={"recipient": "eng@plant.test"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_send" and len(FakeSMTP.sent) == 1
    assert mail_client.post(url, json={"recipient": "other@plant.test"}).status_code == 200      # a different recipient is a deliberate second send


def test_hourly_cap(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir, email_max_per_hour=1, **SMTP_ENV))) as c:
        a = make(c, readings, monkeypatch)
        assert c.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "a@plant.test"}).status_code == 200
        r = c.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "b@plant.test"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "email_rate_limited"


def test_allowed_domains(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir, email_allowed_domains="plant.test", **SMTP_ENV))) as c:
        a = make(c, readings, monkeypatch)
        assert c.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "x@evil.test"}).status_code == 422
        assert c.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "x@plant.test"}).status_code == 200


def test_readings_that_do_not_match_the_saved_result_are_refused(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch, k=2)
    monkeypatch.setattr("app.api.routes_maintenance.score_matrix", lambda b, X: np.tile([0.9, 0.05, 0.05], (len(X), 1)))
    r = mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test", "readings": readings})
    assert r.status_code == 422 and not FakeSMTP.sent


def test_html_in_note_is_escaped(mail_client, readings, monkeypatch):
    a = make(mail_client, readings, monkeypatch)
    mail_client.post(f"{A}/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test", "note": "<script>alert(1)</script>"})
    html = FakeSMTP.sent[0].get_body(("html",)).get_content()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_production_refuses_open_relay():
    with pytest.raises(Exception):
        make_settings("x", environment="production", cors_origins="https://a.test", auto_create_tables=False, **SMTP_ENV)


# ---------- maintenance workflow ----------
def case_for(c, readings, monkeypatch, k=2, **kw):
    a = make(c, readings, monkeypatch, k=k, **kw)
    r = c.post(f"{A}/{a['assessment_id']}/maintenance-case")
    assert r.status_code == 201, r.text
    return a, r.json()["case"]


def upd(c, case, **kw):
    return c.post(f"/api/maintenance-cases/{case['id']}/updates", json=kw)


def test_case_only_for_alert_or_danger_and_only_once(client, readings, monkeypatch):
    n = make(client, readings, monkeypatch, k=0)
    assert client.get(f"{A}/{n['assessment_id']}/maintenance").json()["eligible"] is False
    assert client.post(f"{A}/{n['assessment_id']}/maintenance-case").status_code == 422
    a, case = case_for(client, readings, monkeypatch)
    assert case["status"] == "pending_inspection" and case["reference"].startswith("MC-") and case["updates"][0]["kind"] == "opened"
    assert client.post(f"{A}/{a['assessment_id']}/maintenance-case").status_code == 409
    assert client.get(f"{A}/{a['assessment_id']}/maintenance").json()["eligible"] is False


def test_full_happy_path_preserves_original_and_keeps_log(client, readings, monkeypatch):
    a, case = case_for(client, readings, monkeypatch)
    before = client.get(f"{A}/{a['assessment_id']}").json()
    today = date.today().isoformat()
    r = upd(client, case, to_status="maintenance_in_progress", responsible_engineer="J. Perera", started_on=today, updated_by="JP", fault_found="Noise at drive end")
    assert r.status_code == 200 and r.json()["status"] == "maintenance_in_progress"
    r = upd(client, case, to_status="repair_completed_verification_required", completed_on=today, actions_performed="Work done per site procedure", parts_notes="n/a")
    assert r.status_code == 200 and r.json()["status_label"].startswith("Repair Completed")
    # reassess: a new, separate assessment
    re_ = make(client, readings, monkeypatch, k=0)
    r = client.post(f"/api/maintenance-cases/{case['id']}/reassessments", json={"assessment_id": re_["assessment_id"]})
    assert r.status_code == 200 and r.json()["reassessments"][0]["predicted_condition"] == "Normal"
    assert r.json()["status"] == "repair_completed_verification_required"       # a Normal prediction does NOT close the case
    r = upd(client, case, to_status="verified_closed", verification_outcome="verified", updated_by="J. Perera", comment="Checked under site procedure")
    assert r.status_code == 200 and r.json()["status"] == "verified_closed" and r.json()["allowed_next_statuses"] == []
    kinds = [u["kind"] for u in r.json()["updates"]]
    assert kinds == ["opened", "update", "update", "reassessment", "update"]
    # original assessment untouched
    after = client.get(f"{A}/{a['assessment_id']}").json()
    assert after == before and after["predicted_condition"] == "Danger"
    # closed is final
    assert upd(client, case, to_status="verified_closed", comment="x").status_code == 409
    assert client.post(f"/api/maintenance-cases/{case['id']}/reassessments", json={"assessment_id": re_["assessment_id"]}).status_code == 200


@pytest.mark.parametrize("to", ["repair_completed_verification_required", "verified_closed"])
def test_cannot_skip_steps(client, readings, monkeypatch, to):
    _, case = case_for(client, readings, monkeypatch)
    r = upd(client, case, to_status=to, actions_performed="x", verification_outcome="verified", updated_by="x")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_state"


def test_repair_completion_requires_actions(client, readings, monkeypatch):
    _, case = case_for(client, readings, monkeypatch)
    upd(client, case, to_status="maintenance_in_progress")
    assert upd(client, case, to_status="repair_completed_verification_required").status_code == 422
    assert upd(client, case, to_status="repair_completed_verification_required", actions_performed="  ").status_code == 422


def test_closing_requires_explicit_verification_and_a_name(client, readings, monkeypatch):
    _, case = case_for(client, readings, monkeypatch)
    upd(client, case, to_status="maintenance_in_progress")
    upd(client, case, to_status="repair_completed_verification_required", actions_performed="done")
    assert upd(client, case, to_status="verified_closed", updated_by="JP").status_code == 422
    assert upd(client, case, to_status="verified_closed", verification_outcome="not_verified", updated_by="JP").status_code == 422
    assert upd(client, case, to_status="verified_closed", verification_outcome="verified").status_code == 422
    assert upd(client, case, to_status="verified_closed", verification_outcome="verified", updated_by="JP").status_code == 200


def test_failed_verification_sends_case_back(client, readings, monkeypatch):
    _, case = case_for(client, readings, monkeypatch)
    upd(client, case, to_status="maintenance_in_progress")
    upd(client, case, to_status="repair_completed_verification_required", actions_performed="done")
    assert upd(client, case, to_status="maintenance_in_progress", verification_outcome="not_verified").status_code == 422     # needs a reason
    r = upd(client, case, to_status="maintenance_in_progress", verification_outcome="not_verified", comment="Still noisy")
    assert r.status_code == 200 and r.json()["status"] == "maintenance_in_progress"


def test_note_only_update_in_same_status_and_date_rules(client, readings, monkeypatch):
    _, case = case_for(client, readings, monkeypatch)
    assert upd(client, case, to_status="pending_inspection", comment="Engineer notified").status_code == 200
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert upd(client, case, to_status="maintenance_in_progress", started_on=tomorrow).status_code == 422
    assert upd(client, case, to_status="maintenance_in_progress", started_on="2025-05-02", completed_on="2025-05-01").status_code == 422
    assert upd(client, case, to_status="bogus").status_code == 422
    assert upd(client, case, to_status="maintenance_in_progress", comment="a\x00b").status_code == 422
    assert client.post("/api/maintenance-cases/9999/updates", json={"to_status": "maintenance_in_progress"}).status_code == 404


def test_reassessment_link_rules(client, readings, monkeypatch):
    a, case = case_for(client, readings, monkeypatch, motor="MOT01")
    other = make(client, readings, monkeypatch, k=0, motor="MOT02")
    link = lambda i: client.post(f"/api/maintenance-cases/{case['id']}/reassessments", json={"assessment_id": i})
    same_motor = make(client, readings, monkeypatch, k=0)
    assert link(same_motor["assessment_id"]).status_code == 409                    # repair not completed yet
    upd(client, case, to_status="maintenance_in_progress")
    upd(client, case, to_status="repair_completed_verification_required", actions_performed="done")
    assert link(other["assessment_id"]).status_code == 422                          # different motor
    assert link(a["assessment_id"]).status_code == 422                              # not later than the original
    assert link(99999).status_code == 404
    assert link(same_motor["assessment_id"]).status_code == 200
    again = link(same_motor["assessment_id"])
    assert again.status_code == 200 and len(again.json()["reassessments"]) == 1      # repeating does not duplicate
    d = client.get(f"{A}/{same_motor['assessment_id']}/maintenance").json()
    assert d["follows_assessment_id"] == a["assessment_id"] and d["follows_case_id"] == case["id"]


def test_history_shows_status_filters_and_followups(client, readings, monkeypatch):
    plain = make(client, readings, monkeypatch, k=0, motor="MOT09")
    a, case = case_for(client, readings, monkeypatch, motor="MOT01")
    b, case_b = case_for(client, readings, monkeypatch, motor="MOT02")
    upd(client, case_b, to_status="maintenance_in_progress")
    upd(client, case_b, to_status="repair_completed_verification_required", actions_performed="done")
    upd(client, case_b, to_status="verified_closed", verification_outcome="verified", updated_by="JP")
    get = lambda q="": client.get("/api/predictions" + q).json()
    items = {i["id"]: i for i in get()["items"]}
    assert items[a["assessment_id"]]["maintenance_status"] == "pending_inspection" and items[plain["assessment_id"]]["maintenance_status"] is None
    ids = lambda q: {i["id"] for i in get(q)["items"]}
    assert ids("?maintenance_status=open") == {a["assessment_id"]}
    assert ids("?maintenance_status=pending_inspection") == {a["assessment_id"]}
    assert ids("?maintenance_status=verified_closed") == {b["assessment_id"]}
    assert ids("?maintenance_status=none") == {plain["assessment_id"]}
    assert get("?maintenance_status=open&motor_id=MOT02")["total"] == 0
    assert client.get("/api/predictions?maintenance_status=bogus").status_code == 422
    upd(client, case, to_status="maintenance_in_progress")
    upd(client, case, to_status="repair_completed_verification_required", actions_performed="done")
    re_ = make(client, readings, monkeypatch, k=0, motor="MOT01")
    client.post(f"/api/maintenance-cases/{case['id']}/reassessments", json={"assessment_id": re_["assessment_id"]})
    it = {i["id"]: i for i in get()["items"]}[re_["assessment_id"]]
    assert it["follows_assessment_id"] == a["assessment_id"]
    assert client.get(f"/api/predictions/{re_['assessment_id']}").json()["follows_assessment_id"] == a["assessment_id"]


def test_workflow_survives_restart_with_a_sqlite_file(bundle_dir, readings, monkeypatch, tmp_path):
    cfg = lambda: make_settings(bundle_dir, database_url=f"sqlite:///{tmp_path / 'x.db'}")
    with TestClient(create_app(cfg())) as c:
        a, case = case_for(c, readings, monkeypatch)
        upd(c, case, to_status="maintenance_in_progress", responsible_engineer="JP")
    with TestClient(create_app(cfg())) as c2:
        d = c2.get(f"{A}/{a['assessment_id']}/maintenance").json()
        assert d["case"]["status"] == "maintenance_in_progress" and d["case"]["updates"][-1]["responsible_engineer"] == "JP"
