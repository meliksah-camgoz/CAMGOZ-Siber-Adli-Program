
import hashlib
import json
import getpass

from datetime import datetime, timezone

from sqlalchemy import select

from database.database import SessionLocal
from database.models import AuditEvent


GENESIS_HASH = "0" * 64


def create_event_hash(payload: dict) -> str:

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def add_audit_event(
    session,
    event_type: str,
    evidence_id: int | None = None,
    details: dict | None = None
):

    previous_event = session.scalar(
        select(AuditEvent)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )

    previous_hash = (
        previous_event.event_hash
        if previous_event
        else GENESIS_HASH
    )

    event_time = datetime.now(
        timezone.utc
    ).isoformat()

    actor = getpass.getuser()

    details_json = json.dumps(
        details or {},
        sort_keys=True,
        ensure_ascii=False
    )

    payload = {
        "evidence_id": evidence_id,
        "event_type": event_type,
        "actor": actor,
        "event_time": event_time,
        "details": details_json,
        "previous_hash": previous_hash
    }

    event_hash = create_event_hash(payload)

    event = AuditEvent(
        evidence_id=evidence_id,
        event_type=event_type,
        actor=actor,
        event_time=event_time,
        details=details_json,
        previous_hash=previous_hash,
        event_hash=event_hash
    )

    session.add(event)

    return event


def verify_audit_chain() -> dict:

    with SessionLocal() as session:

        events = session.scalars(
            select(AuditEvent).order_by(AuditEvent.id.asc())
        ).all()

        expected_previous_hash = GENESIS_HASH

        for event in events:

            if event.previous_hash != expected_previous_hash:

                return {
                    "valid": False,
                    "event_id": event.id,
                    "reason": "Previous hash mismatch"
                }

            payload = {
                "evidence_id": event.evidence_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "event_time": event.event_time,
                "details": event.details,
                "previous_hash": event.previous_hash
            }

            calculated_hash = create_event_hash(payload)

            if calculated_hash != event.event_hash:

                return {
                    "valid": False,
                    "event_id": event.id,
                    "reason": "Event hash mismatch"
                }

            expected_previous_hash = event.event_hash

        return {
            "valid": True,
            "total_events": len(events),
            "last_hash": expected_previous_hash
        }
