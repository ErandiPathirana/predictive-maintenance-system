"""Maintenance follow-up rules: which status may follow which, and what must be recorded before a change.

The service never decides that a motor is safe. A case is closed only when a person records that a qualified engineer verified it
under the site's own procedures. A new "Normal" prediction is evidence to show them, not a reason to close.
"""
from __future__ import annotations

from datetime import date

from app.core.errors import MaintenanceInputError, WorkflowStateError

PENDING = "pending_inspection"
IN_PROGRESS = "maintenance_in_progress"
REPAIRED = "repair_completed_verification_required"
CLOSED = "verified_closed"

STATUS_LABELS = {
    PENDING: "Pending Inspection",
    IN_PROGRESS: "Maintenance In Progress",
    REPAIRED: "Repair Completed - Verification Required",
    CLOSED: "Verified / Closed",
}
ALL_STATUSES = (PENDING, IN_PROGRESS, REPAIRED, CLOSED)
OPEN_STATUSES = (PENDING, IN_PROGRESS, REPAIRED)
# Forward steps, plus one step back when verification found that more work is needed.
ALLOWED_NEXT = {PENDING: (IN_PROGRESS,), IN_PROGRESS: (REPAIRED,), REPAIRED: (CLOSED, IN_PROGRESS), CLOSED: ()}

VERIFIED = "verified"
NOT_VERIFIED = "not_verified"
ELIGIBLE_CONDITIONS = ("Alert", "Danger")


def case_reference(case_id: int) -> str:
    return f"MC-{case_id:05d}"


def assessment_reference(assessment_id: int) -> str:
    return f"PM-{assessment_id:06d}"


def check_update(current: str, to: str, f: dict, *, today: date) -> None:
    """Raises WorkflowStateError (not allowed from this status) or MaintenanceInputError (something required is missing)."""
    if to not in ALL_STATUSES:
        raise MaintenanceInputError("Unknown status.", {"allowed": list(ALL_STATUSES)})
    if current == CLOSED:
        raise WorkflowStateError("This case is verified and closed, so it cannot be changed. Start a new follow-up from a new assessment if the motor needs attention again.")
    if to != current and to not in ALLOWED_NEXT[current]:
        nxt = ", ".join(STATUS_LABELS[s] for s in ALLOWED_NEXT[current])
        raise WorkflowStateError(f"The status cannot change from '{STATUS_LABELS[current]}' to '{STATUS_LABELS[to]}'. Allowed next status: {nxt}.",
                                 {"allowed_next": list(ALLOWED_NEXT[current])})
    started, done = f.get("started_on"), f.get("completed_on")
    if started and started > today:
        raise MaintenanceInputError("The maintenance start date cannot be in the future.")
    if done and done > today:
        raise MaintenanceInputError("The completion date cannot be in the future.")
    if started and done and done < started:
        raise MaintenanceInputError("The completion date cannot be before the start date.")
    if to == REPAIRED and current != REPAIRED and not (f.get("actions_performed") or "").strip():
        raise MaintenanceInputError("Record the repair or maintenance actions performed before marking the repair as completed.")
    if current == REPAIRED and to == CLOSED:
        if f.get("verification_outcome") != VERIFIED:
            raise MaintenanceInputError("To close the case, record that a qualified engineer verified the motor under the site's procedures. "
                                        "A new Normal prediction on its own is not verification.")
        if not (f.get("updated_by") or "").strip():
            raise MaintenanceInputError("Enter the name or initials of the person who verified the motor.")
    if current == REPAIRED and to == IN_PROGRESS:
        if f.get("verification_outcome") != NOT_VERIFIED or not (f.get("comment") or "").strip():
            raise MaintenanceInputError("To send the case back to maintenance, choose 'Not verified: more work needed' and say why in the comment.")
