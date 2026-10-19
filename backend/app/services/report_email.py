"""Builds and sends the assessment report e-mail.

* The message is sent only after a person clicks "Send" (nothing is sent automatically).
* Credentials come from environment variables through Settings. They are never written to the log or to the database.
* "Sent" is reported only when the mail server ACCEPTED the message. That is not proof that it reached an inbox.
"""
from __future__ import annotations

import html
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings
from app.core.errors import EmailNotConfiguredError, EmailSendError
from app.services.maintenance import assessment_reference

log = logging.getLogger("app.email")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(\.[A-Za-z0-9\-]{1,63})+$")
PROFESSIONAL_NOTE = ("These results come from a research prototype. They support maintenance decisions but are not a confirmed fault and do not replace "
                     "professional inspection or the site's safety procedures. They require interpretation by a qualified engineer.")


def valid_email(address: str) -> bool:
    return len(address) <= 254 and bool(EMAIL_PATTERN.match(address))


def domain_allowed(settings: Settings, address: str) -> bool:
    allowed = settings.email_allowed_domain_list
    return not allowed or address.rsplit("@", 1)[-1].lower() in allowed


def _lines(row, recs: dict, readings: dict | None, note: str | None, link: str | None) -> list[tuple[str, str]]:
    ref = assessment_reference(row.id)
    out = [("Assessment reference", ref), ("Motor ID", row.motor_id or "Not recorded")]
    if row.equipment_description:
        out.append(("Equipment", row.equipment_description))
    out += [("Readings taken", row.measured_at.strftime("%Y-%m-%d %H:%M") if row.measured_at else "Not recorded"),
            ("Assessment saved (UTC)", row.created_at.strftime("%Y-%m-%d %H:%M")),
            ("Predicted condition", row.predicted_condition),
            ("Model scores", ", ".join(f"{k}: {v:.3f}" for k, v in sorted(row.scores.items(), key=lambda kv: -kv[1])) + " (model outputs, not calibrated probabilities)"),
            ("Model version", row.model_version)]
    steps = [f"{i['priority']}. {i['action']} ({i['timing']}; who: {i['responsible_role']})" for i in recs.get("items", [])]
    out.append(("Recommended next action", recs.get("summary") or "See the assessment record."))
    if steps:
        out.append(("Recommended steps", "\n".join(steps)))
    if readings:
        out.append(("Sensor readings", "\n".join(f"{k}: {v}" for k, v in readings.items())))
    else:
        out.append(("Sensor readings", "Not included. This system does not store raw readings by default."))
    if note:
        out.append(("Sender's note", note))
    if link:
        out.append(("Assessment record", link))
    return out


def build_message(settings: Settings, *, row, recs: dict, recipient: str, readings: dict | None, note: str | None) -> EmailMessage:
    link = f"{settings.public_app_url.rstrip('/')}/#/assessment/{row.id}" if settings.public_app_url else None
    fields = _lines(row, recs, readings, note, link)
    msg = EmailMessage()
    msg["Subject"] = f"[{row.predicted_condition}] Motor {row.motor_id or 'unknown'}: assessment report {assessment_reference(row.id)}"
    msg["From"], msg["To"] = settings.smtp_from, recipient
    text = [f"Motor assessment report: classified {row.predicted_condition}", ""]
    for k, v in fields:
        text += [f"{k}:", *("  " + ln for ln in str(v).split("\n")), ""]
    text += [PROFESSIONAL_NOTE]
    msg.set_content("\n".join(text))
    rows = "".join(f"<tr><th align='left' valign='top'>{html.escape(k)}</th><td>{html.escape(str(v)).replace(chr(10), '<br>')}</td></tr>" for k, v in fields)
    msg.add_alternative(f"<html><body><h2>Motor assessment report: {html.escape(row.predicted_condition)}</h2>"
                        f"<table cellpadding='6' border='1' style='border-collapse:collapse'>{rows}</table><p><em>{html.escape(PROFESSIONAL_NOTE)}</em></p></body></html>",
                        subtype="html")
    return msg


def send_message(settings: Settings, msg: EmailMessage) -> None:
    """Raises EmailNotConfiguredError or EmailSendError. Returns normally only when the server accepted the message for every recipient."""
    if not settings.email_enabled:
        raise EmailNotConfiguredError("E-mail is not set up on this server, so no report was sent. The administrator must set SMTP_HOST and SMTP_FROM.")
    ctx = ssl.create_default_context()
    try:
        if settings.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=ctx)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
        with server:
            if settings.smtp_security == "starttls":
                server.starttls(context=ctx)
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password.get_secret_value() if settings.smtp_password else "")
            refused = server.send_message(msg)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except smtplib.SMTPAuthenticationError as exc:
        log.error("E-mail not sent: the mail server rejected the login (%s)", type(exc).__name__)
        raise EmailSendError("The mail server rejected the sign-in details. The administrator must check SMTP_USERNAME and SMTP_PASSWORD. No report was sent.") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        log.error("E-mail not sent: recipient refused")
        raise EmailSendError("The mail server did not accept that recipient address. No report was sent.") from exc
    except (smtplib.SMTPException, OSError) as exc:        # includes timeouts and connection failures; the message never contains the password
        log.error("E-mail not sent: %s", type(exc).__name__)
        raise EmailSendError("The report could not be sent because the mail server could not be reached or refused the message. Nothing was sent. Try again later.") from exc
