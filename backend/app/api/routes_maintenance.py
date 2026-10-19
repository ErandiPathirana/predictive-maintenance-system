"""Report e-mail and maintenance follow-up. The original assessment row is never modified: follow-up is stored in related tables."""
import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import api_key_guard, get_db, get_settings_dep, get_site_guidance, require_bundle, row_id
from app.core.config import Settings
from app.core.errors import (BadQueryError, DatabaseUnavailableError, DuplicateSendError, InputValidationError, MaintenanceInputError, NotFoundError,
                             RateLimitError, WorkflowStateError, EmailNotConfiguredError, EmailSendError)
from app.db import maintenance_repo as mrepo
from app.db import repository as repo
from app.db.models import MaintenanceCase, Prediction
from app.schemas import ErrorResponse
from app.schemas_workflow import (EmailLogOut, EmailReportRequest, EmailReportResponse, EmailStatus, MaintenanceCaseOut, MaintenanceDetail,
                                  MaintenanceUpdateOut, MaintenanceUpdateRequest, ReassessmentLinkRequest, ReassessmentOut)
from app.services import maintenance as wf
from app.services import report_email as mail
from app.services.assessments import recommendation_for
from app.services.artifacts import LoadedBundle
from app.services.predictions import score_matrix, validate_single_readings
from app.services.recommendations import recommend

router = APIRouter(prefix="/api", dependencies=[Depends(api_key_guard)])
log = logging.getLogger("app.maintenance")
_ERR = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
DUPLICATE_WINDOW_SECONDS = 60


def _need(db: Session, assessment_id: int) -> Prediction:
    row = repo.get_prediction(db, assessment_id)
    if row is None:
        raise NotFoundError("No assessment with that ID.")
    return row


def _eligibility(row: Prediction) -> str | None:
    if row.predicted_condition not in wf.ELIGIBLE_CONDITIONS:
        return "A follow-up case is opened only for Alert or Danger assessments."
    if not row.motor_id:
        return "This assessment has no Motor ID, so it cannot be followed up."
    return None


def _commit(db: Session, what: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.error("%s not saved: database error", what)
        raise DatabaseUnavailableError(f"{what} could not be saved, so nothing was recorded. Please try again.")


def _case_out(db: Session, case: MaintenanceCase) -> MaintenanceCaseOut:
    return MaintenanceCaseOut(
        id=case.id, reference=wf.case_reference(case.id), assessment_id=case.assessment_id, assessment_reference=wf.assessment_reference(case.assessment_id),
        motor_id=case.motor_id, status=case.status, status_label=wf.STATUS_LABELS[case.status], created_at=case.created_at, updated_at=case.updated_at,
        allowed_next_statuses=list(wf.ALLOWED_NEXT[case.status]),
        updates=[MaintenanceUpdateOut.model_validate(u) for u in mrepo.updates_for(db, case.id)],
        reassessments=[ReassessmentOut(assessment_id=r.id, created_at=r.created_at, measured_at=r.measured_at, predicted_condition=r.predicted_condition,
                                       scores=r.scores, readings=r.input_readings) for r in mrepo.reassessment_rows(db, case.id)])


def _detail(db: Session, row: Prediction) -> MaintenanceDetail:
    case = mrepo.get_case_for_assessment(db, row.id)
    why = None if case else _eligibility(row)
    link = mrepo.link_for_reassessment(db, row.id)
    return MaintenanceDetail(
        assessment_id=row.id, predicted_condition=row.predicted_condition, eligible=case is None and why is None, reason=why,
        case=_case_out(db, case) if case else None, emails=[EmailLogOut.model_validate(e) for e in mrepo.emails_for(db, row.id)],
        follows_assessment_id=link and db.get(MaintenanceCase, link.case_id).assessment_id, follows_case_id=link.case_id if link else None)


@router.get("/email-status", response_model=EmailStatus, tags=["Maintenance"], summary="Whether report e-mail is set up (never returns credentials)")
def email_status(settings: Settings = Depends(get_settings_dep)):
    return EmailStatus(configured=settings.email_enabled, recipients_restricted=bool(settings.email_allowed_domain_list),
                       link_in_report=bool(settings.public_app_url), max_per_hour=settings.email_max_per_hour)


@router.post("/assessments/{assessment_id}/email-report", response_model=EmailReportResponse, tags=["Maintenance"], responses={**_ERR, 429: {"model": ErrorResponse},
             502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}, summary="E-mail the report of an Alert or Danger assessment (only when a person asks)")
def email_report(body: EmailReportRequest, assessment_id: int = row_id(), bundle: LoadedBundle = Depends(require_bundle),
                 settings: Settings = Depends(get_settings_dep), site=Depends(get_site_guidance), db: Session = Depends(get_db)):
    row = _need(db, assessment_id)
    if row.predicted_condition not in wf.ELIGIBLE_CONDITIONS:
        raise MaintenanceInputError("Reports are e-mailed only for Alert or Danger assessments.")
    if not settings.email_enabled:
        raise EmailNotConfiguredError("E-mail is not set up on this server, so no report was sent. The administrator must set SMTP_HOST and SMTP_FROM.")
    if not mail.valid_email(body.recipient):
        raise MaintenanceInputError("Enter one valid e-mail address, for example name@company.com.")
    if not mail.domain_allowed(settings, body.recipient):
        raise MaintenanceInputError("That e-mail domain is not on the approved list for this server.")
    if mrepo.recent_sent(db, row.id, body.recipient, DUPLICATE_WINDOW_SECONDS):
        raise DuplicateSendError("This report was already sent to that address a moment ago. It was not sent again.")
    if mrepo.sent_in_last_hour(db) >= settings.email_max_per_hour:
        raise RateLimitError("The hourly e-mail limit for this server has been reached. Try again later.")
    readings = row.input_readings
    if readings is None and body.readings is not None:
        # The server did not keep the readings, so the browser supplies them. They are accepted only if the model reproduces the saved result.
        X = validate_single_readings(body.readings, bundle)
        scores = score_matrix(bundle, X)
        same = (bundle.class_names[int(scores[0].argmax())] == row.predicted_condition
                and all(abs(float(s) - row.scores.get(c, -1.0)) < 1e-6 for c, s in zip(bundle.class_names, scores[0])))
        if not same:
            raise InputValidationError("The readings do not reproduce the saved result, so they were not included and no report was sent.")
        readings = {n: float(v) for n, v in zip(bundle.feature_names, X[0])}
    recs = row.recommendations or recommend(row.predicted_condition, (), site).to_dict()
    msg = mail.build_message(settings, row=row, recs=recs, recipient=body.recipient, readings=readings, note=body.note)
    try:
        mail.send_message(settings, msg)
    except EmailSendError as exc:
        mrepo.log_email(db, row.id, body.recipient, "failed", exc.message[:200])
        _commit(db, "The e-mail attempt")
        raise
    e = mrepo.log_email(db, row.id, body.recipient, "sent")
    _commit(db, "The e-mail record")
    log.info("Report for assessment %s accepted by the mail server", row.id)
    return EmailReportResponse(sent=True, assessment_id=row.id, reference=wf.assessment_reference(row.id), recipient=body.recipient, sent_at=e.created_at,
                               readings_included=readings is not None,
                               message="The mail server accepted the report. This does not guarantee it reached the inbox; confirm with the engineer.")


@router.get("/assessments/{assessment_id}/maintenance", response_model=MaintenanceDetail, responses=_ERR, tags=["Maintenance"],
            summary="Maintenance case, report e-mails and reassessment links for an assessment")
def get_maintenance(assessment_id: int = row_id(), db: Session = Depends(get_db)):
    return _detail(db, _need(db, assessment_id))


@router.post("/assessments/{assessment_id}/maintenance-case", response_model=MaintenanceDetail, status_code=201, responses=_ERR, tags=["Maintenance"],
             summary="Open a follow-up case (status Pending Inspection) for an Alert or Danger assessment")
def open_case(assessment_id: int = row_id(), db: Session = Depends(get_db)):
    row = _need(db, assessment_id)
    if mrepo.get_case_for_assessment(db, row.id):
        raise WorkflowStateError("A follow-up case already exists for this assessment.")
    why = _eligibility(row)
    if why:
        raise MaintenanceInputError(why)
    try:
        mrepo.open_case(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise WorkflowStateError("A follow-up case already exists for this assessment.")
    except SQLAlchemyError:
        db.rollback()
        raise DatabaseUnavailableError("The follow-up case could not be saved, so nothing was recorded. Please try again.")
    return _detail(db, row)


@router.post("/maintenance-cases/{case_id}/updates", response_model=MaintenanceCaseOut, responses=_ERR, tags=["Maintenance"],
             summary="Record a status change or note on a case (appended; earlier entries are never edited)")
def add_case_update(body: MaintenanceUpdateRequest, case_id: int = row_id(), db: Session = Depends(get_db)):
    case = mrepo.get_case(db, case_id)
    if case is None:
        raise NotFoundError("No maintenance case with that ID.")
    fields = body.model_dump(exclude={"to_status"})
    wf.check_update(case.status, body.to_status, fields, today=date.today())
    mrepo.add_update(db, case, kind="update", to_status=body.to_status, **fields)
    _commit(db, "The maintenance update")
    return _case_out(db, case)


@router.post("/maintenance-cases/{case_id}/reassessments", response_model=MaintenanceCaseOut, responses=_ERR, tags=["Maintenance"],
             summary="Link a later assessment of the same motor to the case (the new assessment is saved separately, as usual)")
def link_reassessment(body: ReassessmentLinkRequest, case_id: int = row_id(), db: Session = Depends(get_db)):
    case = mrepo.get_case(db, case_id)
    if case is None:
        raise NotFoundError("No maintenance case with that ID.")
    new = _need(db, body.assessment_id)
    existing = mrepo.link_for_reassessment(db, new.id)
    if existing:
        if existing.case_id == case.id:                      # repeat of the same request: nothing changes
            return _case_out(db, case)
        raise WorkflowStateError("That assessment is already linked to another case.")
    if case.status == wf.CLOSED:
        raise WorkflowStateError("This case is verified and closed.")
    if case.status != wf.REPAIRED:
        raise WorkflowStateError("A reassessment can be linked once the repair is marked completed.")
    if new.motor_id != case.motor_id:
        raise MaintenanceInputError("The reassessment is for a different motor than the case.")
    if new.id <= case.assessment_id:
        raise MaintenanceInputError("The reassessment must be a later assessment than the original.")
    try:
        mrepo.add_update(db, case, kind="reassessment", to_status=case.status, reassessment_assessment_id=new.id,
                         reassessment_date=body.reassessment_date or new.created_at.date(),
                         comment=f"Reassessed: model classified the motor as {new.predicted_condition}. This is not verification.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise WorkflowStateError("That assessment is already linked to a case.")
    except SQLAlchemyError:
        db.rollback()
        raise DatabaseUnavailableError("The link could not be saved, so nothing was recorded. Please try again.")
    return _case_out(db, case)
