"""Sends through the REAL smtplib code path to a tiny SMTP receiver on localhost (a real TCP socket, no mocks of smtplib).

This proves our code speaks SMTP correctly and handles a refusing/absent server. It does NOT prove delivery through a real provider (Gmail, Outlook...).
"""
import socket
import threading

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import make_settings


class SinkServer:
    def __init__(self, reject_rcpt=False):
        self.reject_rcpt, self.messages, self.sock = reject_rcpt, [], socket.socket()
        self.sock.bind(("127.0.0.1", 0)); self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._chat, args=(conn,), daemon=True).start()

    def _chat(self, conn):
        f = conn.makefile("rwb")
        send = lambda s: (f.write((s + "\r\n").encode()), f.flush())
        send("220 sink ready")
        data_mode, buf = False, []
        for raw in f:
            line = raw.decode(errors="replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    self.messages.append("\n".join(buf)); data_mode, buf = False, []; send("250 queued")
                else:
                    buf.append(line[1:] if line.startswith("..") else line)
                continue
            cmd = line.upper()
            if cmd.startswith(("EHLO", "HELO")): send("250 sink")
            elif cmd.startswith("MAIL"): send("250 ok")
            elif cmd.startswith("RCPT"): send("550 no such user" if self.reject_rcpt else "250 ok")
            elif cmd.startswith("DATA"): data_mode = True; send("354 go")
            elif cmd.startswith("QUIT"): send("221 bye"); break
            else: send("250 ok")
        conn.close()

    def close(self):
        self.sock.close()


def force_danger(monkeypatch):
    fake = lambda bundle, X: np.tile([0.05, 0.05, 0.9], (len(X), 1))
    monkeypatch.setattr("app.api.routes_assessments.score_matrix", fake)


def app_for(bundle_dir, port):
    return TestClient(create_app(make_settings(bundle_dir, smtp_host="127.0.0.1", smtp_port=port, smtp_security="none", smtp_from="alerts@plant.test",
                                               public_app_url="https://pm.test.invalid", email_allowed_domains="plant.test")))


def test_real_smtp_conversation_delivers_to_the_sink(bundle_dir, readings, monkeypatch):
    force_danger(monkeypatch)
    srv = SinkServer()
    try:
        with app_for(bundle_dir, srv.port) as c:
            a = c.post("/api/assessments", json={"motor_id": "MOT01", "measured_at": "2025-04-01T07:20:00", "readings": readings}).json()
            r = c.post(f"/api/assessments/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"})
            assert r.status_code == 200 and r.json()["sent"] is True
        assert len(srv.messages) == 1
        m = srv.messages[0]
        assert "To: eng@plant.test" in m and "From: alerts@plant.test" in m and "Danger" in m and "MOT01" in m
    finally:
        srv.close()


def test_server_refusing_the_recipient_is_reported_as_failure(bundle_dir, readings, monkeypatch):
    force_danger(monkeypatch)
    srv = SinkServer(reject_rcpt=True)
    try:
        with app_for(bundle_dir, srv.port) as c:
            a = c.post("/api/assessments", json={"motor_id": "MOT01", "measured_at": "2025-04-01T07:20:00", "readings": readings}).json()
            r = c.post(f"/api/assessments/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"})
            assert r.status_code == 502 and r.json()["error"]["code"] == "email_failed"
            assert c.get("/api/predictions").json()["items"][0]["report_sent_at"] is None
        assert srv.messages == []
    finally:
        srv.close()


def test_nothing_listening_is_reported_as_failure(bundle_dir, readings, monkeypatch):
    force_danger(monkeypatch)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()         # a port with nothing on it
    with app_for(bundle_dir, port) as c:
        a = c.post("/api/assessments", json={"motor_id": "MOT01", "measured_at": "2025-04-01T07:20:00", "readings": readings}).json()
        r = c.post(f"/api/assessments/{a['assessment_id']}/email-report", json={"recipient": "eng@plant.test"})
        assert r.status_code == 502 and "Nothing was sent" in r.json()["error"]["message"]
