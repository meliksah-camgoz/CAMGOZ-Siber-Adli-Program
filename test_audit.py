from database.database import init_database
from database.database import SessionLocal

from database.models import AuditEvent
from core.audit_logger import verify_audit_chain

from sqlalchemy import select


def main():

    init_database()

    print("\n========== CAMGOZ AUDIT SYSTEM ==========\n")

    with SessionLocal() as session:

        events = session.scalars(
            select(AuditEvent).order_by(AuditEvent.id.asc())
        ).all()

        print(f"Total audit events: {len(events)}")

        for event in events:

            print("\n------------------------------")
            print(f"Event ID: {event.id}")
            print(f"Type: {event.event_type}")
            print(f"Actor: {event.actor}")
            print(f"Evidence ID: {event.evidence_id}")
            print(f"Time: {event.event_time}")
            print(f"Hash: {event.event_hash}")

    print("\n========== CHAIN VERIFICATION ==========\n")

    result = verify_audit_chain()

    print(result)

    if result["valid"]:
        print("\nAUDIT CHAIN: VALID")
    else:
        print("\nAUDIT CHAIN: INVALID")
        print(f"Problem Event: {result['event_id']}")
        print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    main()
