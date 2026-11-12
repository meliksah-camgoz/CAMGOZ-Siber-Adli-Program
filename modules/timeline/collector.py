"""Unified, read-only event collection for CAMGOZ Timeline Analysis."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select, desc

from database.database import SessionLocal
from database.models import Evidence, AuditEvent, USBDevice, USBActivity
from modules.browser_forensics import detect_profiles, collect_profile_artifacts
from modules.windows_artifacts.recent_files import collect_recent_files


def _normalise_time(value):
    if value is None:
        return ""
    return str(value).strip()


def collect_timeline_events(include_browser=True, include_recent=True):
    """Collect normalized events without writing to any source database."""
    events = []

    # CAMGOZ database sources: evidence, audit and USB artifacts.
    with SessionLocal() as session:
        evidence_rows = session.scalars(
            select(Evidence).order_by(desc(Evidence.analyzed_at)).limit(5000)
        ).all()
        for item in evidence_rows:
            events.append({
                "date": _normalise_time(item.analyzed_at or item.modified_at or item.created_at),
                "source": "Evidence",
                "event_type": "EVIDENCE_ANALYZED",
                "title": item.file_name or "Evidence",
                "details": f"Path: {item.file_path or '-'} | SHA256: {item.sha256 or '-'}",
                "reference": f"Evidence ID: {item.id}",
            })

        audit_rows = session.scalars(
            select(AuditEvent).order_by(desc(AuditEvent.event_time)).limit(10000)
        ).all()
        for item in audit_rows:
            events.append({
                "date": _normalise_time(item.event_time),
                "source": "Audit Trail",
                "event_type": item.event_type or "AUDIT_EVENT",
                "title": item.actor or "CAMGOZ",
                "details": item.details or "",
                "reference": f"Audit ID: {item.id} | Evidence ID: {item.evidence_id or '-'}",
            })

        usb_rows = session.execute(
            select(USBActivity, USBDevice)
            .join(USBDevice, USBActivity.device_id == USBDevice.id)
            .order_by(desc(USBActivity.event_time), desc(USBActivity.id))
            .limit(15000)
        ).all()

        for activity, device in usb_rows:
            is_file = (activity.event_type or "").startswith("FILE_")
            events.append({
                "date": _normalise_time(activity.event_time),
                "source": "USB File Activity" if is_file else "USB Connection",
                "event_type": activity.event_type or "USB_EVENT",
                "title": activity.file_name or device.device_name or "USB Device",
                "details": (
                    f"Device: {device.device_name or '-'} | "
                    f"Drive: {activity.drive_letter or '-'} | "
                    f"Volume: {activity.volume_label or '-'} | "
                    f"Path: {activity.file_path or '-'} | "
                    f"{activity.details or ''}"
                ),
                "reference": (
                    f"USB Activity ID: {activity.id} | Device ID: {device.id} | "
                    f"Session: {activity.session_id or '-'}"
                ),
            })

    if include_browser:
        for profile in detect_profiles():
            try:
                rows = collect_profile_artifacts(profile)
                for item in rows:
                    events.append({
                        "date": _normalise_time(item.get("date")),
                        "source": "Browser",
                        "event_type": f'BROWSER_{(item.get("type") or "ARTIFACT").upper()}',
                        "title": item.get("title") or item.get("url") or "Browser Artifact",
                        "details": (
                            f'Browser: {item.get("browser", "-")} | '
                            f'Profile: {item.get("profile", "-")} | '
                            f'URL: {item.get("url", "-")} | '
                            f'{item.get("details", "")}'
                        ),
                        "reference": f'Profile: {profile.get("profile_path", "")}',
                    })
            except Exception as exc:
                events.append({
                    "date": "",
                    "source": "Browser",
                    "event_type": "BROWSER_READ_ERROR",
                    "title": profile.get("display_name") or profile.get("profile", "Browser Profile"),
                    "details": str(exc),
                    "reference": profile.get("profile_path", ""),
                })

    if include_recent:
        try:
            for item in collect_recent_files():
                events.append({
                    "date": _normalise_time(
                        item.get("shortcut_modified_at") or item.get("shortcut_created_at")
                    ),
                    "source": "Recent Files",
                    "event_type": "RECENT_FILE_SHORTCUT",
                    "title": item.get("shortcut_name") or "Recent File",
                    "details": (
                        f'Target: {item.get("target_path") or "-"} | '
                        f'Status: {item.get("parse_status") or "-"} | '
                        f'Description: {item.get("description") or ""}'
                    ),
                    "reference": item.get("shortcut_path") or "",
                })
        except Exception as exc:
            events.append({
                "date": "",
                "source": "Recent Files",
                "event_type": "RECENT_FILES_READ_ERROR",
                "title": "Recent Files collection failed",
                "details": str(exc),
                "reference": "",
            })

    # ISO-like timestamps sort lexicographically; unknown dates are placed last.
    events.sort(key=lambda event: event["date"], reverse=True)
    return events
