"""Database reads and writes for maintenance cases, their update log and report e-mail attempts."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MaintenanceCase, MaintenanceUpdate, Prediction, ReportEmail


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_case_for_assessment(db: Session, assessment_id: int) -> MaintenanceCase | None:
    return db.scalar(select(MaintenanceCase).where(MaintenanceCase.assessment_id == assessment_id))


def get_case(db: Session, case_id: int) -> MaintenanceCase | None:
    return db.get(MaintenanceCase, case_id)


def updates_for(db: Session, case_id: int) -> list[MaintenanceUpdate]:
    return list(db.scalars(select(MaintenanceUpdate).where(MaintenanceUpdate.case_id == case_id).order_by(MaintenanceUpdate.id)))


def reassessment_rows(db: Session, case_id: int) -> list[Prediction]:
    return list(db.scalars(select(Prediction).join(MaintenanceUpdate, MaintenanceUpdate.reassessment_assessment_id == Prediction.id)
                           .where(MaintenanceUpdate.case_id == case_id).order_by(Prediction.id)))


def link_for_reassessment(db: Session, assessment_id: int) -> MaintenanceUpdate | None:
    return db.scalar(select(MaintenanceUpdate).where(MaintenanceUpdate.reassessment_assessment_id == assessment_id))


def open_case(db: Session, row: Prediction) -> MaintenanceCase:
    now = utcnow()
    case = MaintenanceCase(assessment_id=row.id, motor_id=row.motor_id, status="pending_inspection", created_at=now, updated_at=now)
    db.add(case)
    db.flush()
    db.add(MaintenanceUpdate(case_id=case.id, created_at=now, kind="opened", from_status=None, to_status="pending_inspection"))
    db.flush()
    return case


def add_update(db: Session, case: MaintenanceCase, *, kind: str, to_status: str, **fields) -> MaintenanceUpdate:
    now = utcnow()
    upd = MaintenanceUpdate(case_id=case.id, created_at=now, kind=kind, from_status=case.status, to_status=to_status, **fields)
    db.add(upd)
    case.status, case.updated_at = to_status, now
    db.flush()
    return upd


def emails_for(db: Session, assessment_id: int) -> list[ReportEmail]:
    return list(db.scalars(select(ReportEmail).where(ReportEmail.assessment_id == assessment_id).order_by(ReportEmail.id.desc())))


def log_email(db: Session, assessment_id: int, recipient: str, status: str, error: str | None = None) -> ReportEmail:
    e = ReportEmail(assessment_id=assessment_id, recipient=recipient, status=status, error_summary=error, created_at=utcnow())
    db.add(e)
    db.flush()
    return e


def recent_sent(db: Session, assessment_id: int, recipient: str, seconds: int) -> bool:
    since = utcnow() - timedelta(seconds=seconds)
    return db.scalar(select(func.count()).select_from(ReportEmail).where(
        ReportEmail.assessment_id == assessment_id, ReportEmail.recipient == recipient, ReportEmail.status == "sent", ReportEmail.created_at >= since)) > 0


def sent_in_last_hour(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ReportEmail).where(
        ReportEmail.status == "sent", ReportEmail.created_at >= utcnow() - timedelta(hours=1))) or 0


def history_extras(db: Session, ids: list[int]) -> dict[int, dict]:
    """Maintenance status, last successful e-mail and 'follows' link for a page of assessment IDs (three queries, not one per row)."""
    out = {i: {"maintenance_status": None, "maintenance_case_id": None, "report_sent_at": None, "follows_assessment_id": None} for i in ids}
    if not ids:
        return out
    for c in db.scalars(select(MaintenanceCase).where(MaintenanceCase.assessment_id.in_(ids))):
        out[c.assessment_id].update(maintenance_status=c.status, maintenance_case_id=c.id)
    for aid, last in db.execute(select(ReportEmail.assessment_id, func.max(ReportEmail.created_at)).where(
            ReportEmail.assessment_id.in_(ids), ReportEmail.status == "sent").group_by(ReportEmail.assessment_id)):
        out[aid]["report_sent_at"] = last
    for u, origin in db.execute(select(MaintenanceUpdate, MaintenanceCase.assessment_id).join(MaintenanceCase, MaintenanceCase.id == MaintenanceUpdate.case_id)
                                .where(MaintenanceUpdate.reassessment_assessment_id.in_(ids))):
        out[u.reassessment_assessment_id]["follows_assessment_id"] = origin
        out[u.reassessment_assessment_id]["maintenance_case_id"] = u.case_id
    return out
