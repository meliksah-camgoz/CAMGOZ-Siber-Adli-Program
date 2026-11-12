from pathlib import Path

from sqlalchemy import select

from core.audit_logger import add_audit_event
from core.hash_engine import calculate_file_hashes
from database.database import SessionLocal
from database.models import AuditEvent, Evidence


class EvidenceManager:
    @staticmethod
    def add_evidence(analysis_result: dict, notes: str = "") -> int:
        """Save evidence and create an audit event."""
        with SessionLocal() as session:
            evidence = Evidence(
                file_name=analysis_result["file_name"],
                file_path=analysis_result["file_path"],
                file_size=analysis_result["file_size"],
                file_type=analysis_result["file_type"],
                extension=analysis_result["extension"],
                md5=analysis_result["md5"],
                sha256=analysis_result["sha256"],
                created_at=analysis_result["created_at"],
                modified_at=analysis_result["modified_at"],
                accessed_at=analysis_result["accessed_at"],
                analyzed_at=analysis_result["analyzed_at"],
                notes=notes,
            )

            session.add(evidence)
            session.flush()

            add_audit_event(
                session=session,
                event_type="EVIDENCE_ADDED",
                evidence_id=evidence.id,
                details={
                    "file_name": evidence.file_name,
                    "file_path": evidence.file_path,
                    "sha256": evidence.sha256,
                    "md5": evidence.md5,
                },
            )

            session.commit()
            return evidence.id

    @staticmethod
    def _get_archive_states(session) -> dict[int, str]:
        """
        Return the latest archive/restore action for each evidence ID.
        Events are ordered newest first, so the first action per ID wins.
        """
        events = session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.event_type.in_(
                    ("EVIDENCE_ARCHIVED", "EVIDENCE_RESTORED")
                ),
                AuditEvent.evidence_id.is_not(None),
            )
            .order_by(AuditEvent.id.desc())
        ).all()

        states = {}
        for event in events:
            if event.evidence_id not in states:
                states[event.evidence_id] = event.event_type

        return states

    @staticmethod
    def get_all_evidence() -> list:
        """Retrieve active evidence records only."""
        with SessionLocal() as session:
            states = EvidenceManager._get_archive_states(session)
            archived_ids = [
                evidence_id
                for evidence_id, state in states.items()
                if state == "EVIDENCE_ARCHIVED"
            ]

            statement = select(Evidence)
            if archived_ids:
                statement = statement.where(
                    Evidence.id.not_in(archived_ids)
                )

            statement = statement.order_by(Evidence.id.desc())
            return list(session.scalars(statement).all())

    @staticmethod
    def get_evidence_by_id(evidence_id: int):
        """Retrieve evidence by ID."""
        with SessionLocal() as session:
            return session.get(Evidence, evidence_id)

    @staticmethod
    def count_evidence() -> int:
        """Return the number of active evidence records."""
        return len(EvidenceManager.get_all_evidence())

    @staticmethod
    def verify_evidence_integrity(evidence_id: int) -> dict:
        """
        Verify whether the original evidence file still matches
        its recorded SHA256 hash and write the result to the audit log.
        """
        with SessionLocal() as session:
            evidence = session.get(Evidence, evidence_id)

            if evidence is None:
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "message": "Evidence record not found.",
                }

            file_path = Path(evidence.file_path)

            if not file_path.is_file():
                result = {
                    "success": False,
                    "status": "FILE_MISSING",
                    "message": "Original evidence file is missing.",
                }
            else:
                current_hashes = calculate_file_hashes(str(file_path))
                original_hash = evidence.sha256.lower()
                current_hash = current_hashes["sha256"].lower()
                is_valid = original_hash == current_hash

                result = {
                    "success": True,
                    "status": (
                        "INTEGRITY_VERIFIED"
                        if is_valid
                        else "INTEGRITY_FAILED"
                    ),
                    "original_sha256": original_hash,
                    "current_sha256": current_hash,
                    "message": (
                        "Evidence integrity verified."
                        if is_valid
                        else "Evidence file has been modified!"
                    ),
                }

            add_audit_event(
                session=session,
                event_type="EVIDENCE_INTEGRITY_CHECK",
                evidence_id=evidence.id,
                details=result,
            )
            session.commit()
            return result

    @staticmethod
    def archive_evidence(evidence_id: int) -> bool:
        """
        Archive an active evidence record.
        The evidence row and original file are preserved.
        """
        with SessionLocal() as session:
            evidence = session.get(Evidence, evidence_id)
            if evidence is None:
                raise ValueError("Evidence record not found.")

            states = EvidenceManager._get_archive_states(session)
            if states.get(evidence_id) == "EVIDENCE_ARCHIVED":
                return False

            add_audit_event(
                session=session,
                event_type="EVIDENCE_ARCHIVED",
                evidence_id=evidence_id,
                details={
                    "file_name": evidence.file_name,
                    "sha256": evidence.sha256,
                    "action": "Evidence removed from active list",
                    "original_file_deleted": False,
                },
            )
            session.commit()
            return True

    @staticmethod
    def restore_evidence(evidence_id: int) -> bool:
        """
        Restore an archived evidence record to the active list.
        The original file is not moved, copied, or modified.
        """
        with SessionLocal() as session:
            evidence = session.get(Evidence, evidence_id)
            if evidence is None:
                raise ValueError("Evidence record not found.")

            states = EvidenceManager._get_archive_states(session)
            if states.get(evidence_id) != "EVIDENCE_ARCHIVED":
                return False

            add_audit_event(
                session=session,
                event_type="EVIDENCE_RESTORED",
                evidence_id=evidence_id,
                details={
                    "file_name": evidence.file_name,
                    "sha256": evidence.sha256,
                    "action": "Evidence restored to active list",
                    "original_file_modified": False,
                },
            )
            session.commit()
            return True

    @staticmethod
    def get_archived_evidence() -> list:
        """Retrieve evidence whose latest archive/restore action is archive."""
        with SessionLocal() as session:
            states = EvidenceManager._get_archive_states(session)
            archived_ids = [
                evidence_id
                for evidence_id, state in states.items()
                if state == "EVIDENCE_ARCHIVED"
            ]

            if not archived_ids:
                return []

            statement = (
                select(Evidence)
                .where(Evidence.id.in_(archived_ids))
                .order_by(Evidence.id.desc())
            )
            return list(session.scalars(statement).all())
