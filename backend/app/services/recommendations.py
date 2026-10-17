"""Corrective-action recommendations for a predicted motor condition.

This module is deliberately SEPARATE from the machine-learning model:
  * It receives the model's predicted class NAME (never a class index) and, optionally, the names of input features that were
    flagged as outside the range seen in training.
  * It never looks at sensor values to decide that something is "too high". There are no verified engineering thresholds in this
    project, so none are invented. See docs/recommendation-rules.md.
  * Every recommendation says where it comes from. Built-in rules are GENERAL GUIDANCE that a maintenance engineer must confirm.
    Only actions loaded from an approved site-guidance file (see load_site_guidance) are labelled as site-approved.
  * It gives advice only. It never issues a command and never claims a mechanical diagnosis.

Change the wording or rules here, bump RULESET_VERSION, and update the tests and docs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

RULESET_VERSION = "general-guidance-1.1"

# Timing categories, from most to least urgent. Exact repair deadlines are NOT defined here: they must come from site procedures.
TIMING_IMMEDIATE = "Immediate safety review"
TIMING_PROMPT = "Prompt engineering assessment"
TIMING_PLANNED = "Planned maintenance review"
TIMING_ROUTINE = "Routine monitoring"
TIMING_ORDER = (TIMING_IMMEDIATE, TIMING_PROMPT, TIMING_PLANNED, TIMING_ROUTINE)

SOURCE_GENERAL = "general_guidance"
SOURCE_SITE = "site_approved"

GENERAL_SOURCE_TEXT = "General guidance. Requires maintenance-engineer confirmation. No site-approved procedure is configured for this action."

DISCLAIMER = (
    "This is decision support from a research prototype, not a safety-rated control system. It does not issue shutdown commands and "
    "does not diagnose a fault. Site safety procedures and qualified personnel always take precedence."
)
THRESHOLD_NOTE = (
    "These recommendations follow the model's predicted class only. No approved engineering thresholds are configured, "
    "so no sensor value is judged high or low here. Thresholds need approval from a qualified engineer before they can be used."
)
UNKNOWN_CLASS_NOTE = (
    "The model returned a class this system has no recommendation rules for. No recommendation was generated. "
    "Ask the maintenance engineer to review the reading directly."
)

NORMAL, ALERT, DANGER = "Normal", "Alert", "Danger"
KNOWN_CONDITIONS = (NORMAL, ALERT, DANGER)

ROLE_OPERATOR = "Machine operator"
ROLE_SUPERVISOR = "Shift supervisor"
ROLE_ENGINEER = "Responsible maintenance engineer"
ROLE_QUALIFIED = "Qualified maintenance personnel"
ROLES = (ROLE_OPERATOR, ROLE_SUPERVISOR, ROLE_ENGINEER, ROLE_QUALIFIED)


@dataclass(frozen=True)
class Recommendation:
    priority: int                       # 1 = first thing to do
    action: str
    reason: str
    responsible_role: str
    timing: str
    source: str                         # SOURCE_GENERAL or SOURCE_SITE
    source_detail: str
    safety_note: str | None = None
    requires_confirmation: bool = True  # False only for site-approved actions

    def to_dict(self) -> dict:
        return {
            "priority": self.priority, "action": self.action, "reason": self.reason, "responsible_role": self.responsible_role,
            "timing": self.timing, "safety_note": self.safety_note, "source": self.source, "source_detail": self.source_detail,
            "requires_confirmation": self.requires_confirmation,
        }


RETURN_TO_SERVICE_NOTE = (
    "These are questions to settle, not pass/fail criteria. This system cannot decide that a motor is safe to return to service. "
    "The actual criteria must come from the site's approved procedures, and the decision belongs to authorised, qualified personnel."
)
_RETURN_TO_SERVICE = (
    "A qualified person has inspected the motor and recorded what they found.",
    "The reason for the predicted condition has been identified, or ruled out, by that inspection. This system does not identify causes.",
    "Any repair or adjustment was carried out under the approved maintenance procedure and recorded.",
    "A new measurement has been taken after the inspection and entered here, and its predicted condition has been reviewed by the maintenance engineer.",
    "Return to service has been authorised under the site's procedure, including removal of any lockout/tagout by the authorised person.",
)


@dataclass(frozen=True)
class RecommendationSet:
    condition: str
    available: bool                     # False for an unknown class: nothing is invented
    ruleset_version: str
    headline: str
    items: tuple[Recommendation, ...]
    summary: str                        # short text suitable for storing with the assessment
    disclaimer: str = DISCLAIMER
    threshold_note: str = THRESHOLD_NOTE
    site_guidance_version: str | None = None
    urgent: bool = False                # True for Danger: the page shows a prominent notice
    return_to_service: tuple[str, ...] = ()   # questions to settle before the motor returns to service (Alert and Danger only)
    return_to_service_note: str | None = None

    def to_dict(self) -> dict:
        return {
            "condition": self.condition, "available": self.available, "ruleset_version": self.ruleset_version,
            "headline": self.headline, "items": [i.to_dict() for i in self.items], "summary": self.summary,
            "disclaimer": self.disclaimer, "threshold_note": self.threshold_note,
            "site_guidance_version": self.site_guidance_version, "urgent": self.urgent,
            "return_to_service": list(self.return_to_service), "return_to_service_note": self.return_to_service_note,
        }


# ---------------------------------------------------------------- site-approved guidance (optional) ----------
@dataclass(frozen=True)
class SiteAction:
    action: str
    reason: str
    responsible_role: str
    timing: str
    procedure_ref: str
    safety_note: str | None = None


@dataclass(frozen=True)
class SiteGuidance:
    guidance_version: str
    approved_by: str
    approved_on: date
    actions: dict[str, tuple[SiteAction, ...]] = field(default_factory=dict)


class SiteGuidanceError(ValueError):
    """The site-guidance file is missing something. The file is refused as a whole, never half-used."""


_TEXT = re.compile(r"^.{1,500}$", re.S)


def _req(d: dict, key: str, where: str, max_len: int = 500) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip() or len(v) > max_len:
        raise SiteGuidanceError(f"{where}: '{key}' must be non-empty text of at most {max_len} characters.")
    return v.strip()


def parse_site_guidance(data: object) -> SiteGuidance:
    """Validates an approved-guidance document. Required: who approved it, when, and a procedure reference for every action."""
    if not isinstance(data, dict):
        raise SiteGuidanceError("The guidance file must contain a JSON object.")
    version = _req(data, "guidance_version", "file", 64)
    approved_by = _req(data, "approved_by", "file", 120)
    try:
        approved_on = date.fromisoformat(_req(data, "approved_on", "file", 10))
    except ValueError as exc:
        raise SiteGuidanceError("file: 'approved_on' must be a date like 2026-03-01.") from exc
    conditions = data.get("conditions")
    if not isinstance(conditions, dict) or not conditions:
        raise SiteGuidanceError("file: 'conditions' must list at least one condition.")
    out: dict[str, tuple[SiteAction, ...]] = {}
    for cond, items in conditions.items():
        if cond not in KNOWN_CONDITIONS:
            raise SiteGuidanceError(f"Unknown condition '{cond}'. Allowed: {', '.join(KNOWN_CONDITIONS)}.")
        if not isinstance(items, list) or not items:
            raise SiteGuidanceError(f"{cond}: must be a non-empty list of actions.")
        parsed = []
        for n, it in enumerate(items, 1):
            where = f"{cond} action {n}"
            if not isinstance(it, dict):
                raise SiteGuidanceError(f"{where}: must be an object.")
            timing = _req(it, "timing", where, 64)
            if timing not in TIMING_ORDER:
                raise SiteGuidanceError(f"{where}: 'timing' must be one of {', '.join(TIMING_ORDER)}.")
            note = it.get("safety_note")
            if note is not None and (not isinstance(note, str) or not note.strip() or len(note) > 500):
                raise SiteGuidanceError(f"{where}: 'safety_note' must be text of at most 500 characters, or left out.")
            parsed.append(SiteAction(_req(it, "action", where), _req(it, "reason", where), _req(it, "responsible_role", where, 120), timing,
                                     _req(it, "procedure_ref", where, 200), note.strip() if note else None))
        out[cond] = tuple(parsed)
    return SiteGuidance(version, approved_by, approved_on, out)


def load_site_guidance(path: str | Path) -> SiteGuidance:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SiteGuidanceError(f"Site guidance file not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise SiteGuidanceError(f"Site guidance file is not valid JSON: {exc.msg}") from exc
    return parse_site_guidance(data)


# ---------------------------------------------------------------- built-in general guidance ----------
def _g(priority: int, action: str, reason: str, role: str, timing: str, safety: str | None = None) -> Recommendation:
    return Recommendation(priority, action, reason, role, timing, SOURCE_GENERAL, GENERAL_SOURCE_TEXT, safety, True)


_NORMAL = (
    _g(1, "Continue routine monitoring according to the approved maintenance schedule.",
       "The model classed these readings as Normal. This is not a guarantee that the motor is healthy.", ROLE_OPERATOR, TIMING_ROUTINE),
    _g(2, "Review the motor's historical trend for unexpected changes.",
       "A single reading cannot show a slow change. Trends are easier to judge over time.", ROLE_ENGINEER, TIMING_ROUTINE),
    _g(3, "Record this assessment.", "A complete record makes later comparison possible.", ROLE_OPERATOR, TIMING_ROUTINE),
    _g(4, "Follow the existing preventive-maintenance plan.", "A Normal prediction does not take the place of planned maintenance.", ROLE_ENGINEER, TIMING_PLANNED),
)

_ALERT = (
    _g(1, "Notify the responsible maintenance engineer.",
       "An Alert needs a person with the right knowledge to decide what happens next.", ROLE_OPERATOR, TIMING_PROMPT),
    _g(2, "Review the current and historical sensor readings for this motor.",
       "Comparing with earlier readings shows whether this is a one-off or a change over time.", ROLE_ENGINEER, TIMING_PROMPT),
    _g(3, "Repeat or verify the measurement if appropriate.",
       "A repeat reading helps rule out a measurement or data-entry error.", ROLE_OPERATOR, TIMING_PROMPT),
    _g(4, "Inspect the motor and relevant components according to the approved inspection procedure. Where relevant to the equipment and "
          "the inspection plan, look for unusual noise, heat, looseness, alignment problems or lubrication issues.",
       "An Alert is a prediction, not a confirmed fault diagnosis. An inspection is how it is confirmed or dismissed.",
       ROLE_QUALIFIED, TIMING_PROMPT,
       "Inspect only as the approved procedure allows. Follow lockout/tagout where the procedure requires it."),
    _g(5, "Change how often this motor is monitored only if an approved maintenance procedure allows it.",
       "Monitoring frequency is a site decision, not something this system sets.", ROLE_ENGINEER, TIMING_PLANNED),
)

_DANGER = (
    _g(1, "Notify the responsible maintenance engineer immediately.",
       "Danger is the most serious class the model predicts. A qualified person must assess it now.", ROLE_OPERATOR, TIMING_IMMEDIATE,
       "If you see signs of an immediate hazard, such as smoke, burning smell, sparks or severe vibration, follow the site's emergency procedure first."),
    _g(2, "If the equipment may be unsafe to run, stop or isolate it only through the site's approved shutdown, lockout/tagout and authorisation procedures.",
       "This system cannot judge whether the equipment is unsafe and does not control the machine. That decision belongs to authorised personnel.",
       ROLE_SUPERVISOR, TIMING_IMMEDIATE,
       "Do not open electrical equipment, remove guards or touch moving parts unless you are qualified and authorised."),
    _g(3, "Arrange a qualified inspection before the equipment returns to service, where site procedures require it.",
       "A Danger prediction is not a confirmed fault. Only an inspection can confirm or dismiss it.", ROLE_QUALIFIED, TIMING_PROMPT),
    _g(4, "Record the sensor readings, the model output, the timestamp and every action taken.",
       "A complete record supports the investigation and later review.", ROLE_OPERATOR, TIMING_PROMPT),
    _g(5, "Check the approved maintenance instructions before deciding on any repair.",
       "The model does not identify a mechanical cause. Repairs need a qualified diagnosis.", ROLE_ENGINEER, TIMING_PROMPT),
)

_BY_CONDITION = {NORMAL: _NORMAL, ALERT: _ALERT, DANGER: _DANGER}

_HEADLINES = {
    NORMAL: "Predicted condition: Normal. Continue routine monitoring.",
    ALERT: "Predicted condition: Alert. Have a maintenance engineer review this motor.",
    DANGER: "Predicted condition: Danger. Tell a maintenance engineer now and follow site safety procedures.",
}


def _data_check(features: tuple[str, ...]) -> Recommendation:
    shown = ", ".join(features[:4]) + (f" and {len(features) - 4} more" if len(features) > 4 else "")
    return Recommendation(
        0, "Check that the flagged readings were measured and entered correctly.",
        f"These readings are outside the range seen when the model was trained ({shown}). The model is less reliable outside that range.",
        ROLE_OPERATOR, TIMING_PROMPT, SOURCE_GENERAL, GENERAL_SOURCE_TEXT, None, True)


def _summary(condition: str, items: tuple[Recommendation, ...]) -> str:
    first = items[0].action if items else ""
    return f"{condition}: {len(items)} recommended action{'s' if len(items) != 1 else ''}. First: {first}"[:500]


def recommend(predicted_condition: str, out_of_range_features: Iterable[str] = (), site_guidance: SiteGuidance | None = None) -> RecommendationSet:
    """Recommendations for one predicted condition.

    predicted_condition: the class NAME returned by the model's class mapping (exact match, e.g. "Danger").
    out_of_range_features: names of inputs flagged as outside the training range (a data-quality hint, not an engineering limit).
    site_guidance: approved site actions, if the site supplied any. They are added after the general guidance and labelled as site-approved.
    """
    condition = predicted_condition if isinstance(predicted_condition, str) else str(predicted_condition)
    base = _BY_CONDITION.get(condition)
    if base is None:
        return RecommendationSet(condition=condition, available=False, ruleset_version=RULESET_VERSION,
                                 headline="No recommendation available for this predicted class.", items=(),
                                 summary=f"{condition}: no recommendation generated (unknown class).", disclaimer=DISCLAIMER + " " + UNKNOWN_CLASS_NOTE)
    flagged = tuple(dict.fromkeys(out_of_range_features))
    ordered: list[Recommendation] = list(base)
    if flagged:
        ordered.insert(1 if condition == DANGER else 0, _data_check(flagged))   # for Danger, "notify the engineer" always stays first
    site_version = None
    if site_guidance is not None and condition in site_guidance.actions:
        site_version = site_guidance.guidance_version
        for sa in site_guidance.actions[condition]:
            ordered.append(Recommendation(0, sa.action, sa.reason, sa.responsible_role, sa.timing, SOURCE_SITE,
                                          f"Site-approved: {sa.procedure_ref} (guidance {site_guidance.guidance_version}, approved by "
                                          f"{site_guidance.approved_by} on {site_guidance.approved_on.isoformat()})", sa.safety_note, False))
    numbered = tuple(Recommendation(n, r.action, r.reason, r.responsible_role, r.timing, r.source, r.source_detail, r.safety_note,
                                    r.requires_confirmation) for n, r in enumerate(ordered, 1))
    return RecommendationSet(condition=condition, available=True, ruleset_version=RULESET_VERSION, headline=_HEADLINES[condition], items=numbered,
                             summary=_summary(condition, numbered), site_guidance_version=site_version, urgent=condition == DANGER,
                             return_to_service=_RETURN_TO_SERVICE if condition in (ALERT, DANGER) else (),
                             return_to_service_note=RETURN_TO_SERVICE_NOTE if condition in (ALERT, DANGER) else None)
