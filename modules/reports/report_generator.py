import json
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from sqlalchemy import select

from core.audit_logger import verify_audit_chain
from database.database import SessionLocal
from database.models import AuditEvent, Evidence


def _register_fonts():
    """Register a Unicode font so Turkish characters render correctly."""
    candidates = [
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    ]

    for regular, bold in candidates:
        if os.path.isfile(regular) and os.path.isfile(bold):
            if "CAMGOZ" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("CAMGOZ", regular))
                pdfmetrics.registerFont(TTFont("CAMGOZ-Bold", bold))
                pdfmetrics.registerFontFamily(
                    "CAMGOZ", normal="CAMGOZ",
                    bold="CAMGOZ-Bold", italic="CAMGOZ",
                    boldItalic="CAMGOZ-Bold"
                )
            return "CAMGOZ", "CAMGOZ-Bold"

    raise RuntimeError(
        "Türkçe karakter destekli yazı tipi bulunamadı. "
        "Windows Arial yazı tipinin yüklü olduğundan emin olun."
    )


def _safe(value):
    if value is None or value == "":
        return "-"
    return escape(str(value))


def _format_size(size):
    size = int(size or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"
    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.2f} MB"
    return f"{size / (1024 ** 3):.2f} GB"



def _latest_status(events):
    checks = [
        event for event in events
        if event["event_type"] == "EVIDENCE_INTEGRITY_CHECK"
    ]

    if not checks:
        return "NOT_CHECKED", None

    event = checks[-1]

    try:
        details = json.loads(event["details"] or "{}")
    except (ValueError, TypeError):
        details = {}

    return details.get("status", "UNKNOWN"), event


def _archive_status(events):
    for event in reversed(events):
        if event["event_type"] == "EVIDENCE_ARCHIVED":
            return "ARCHIVED"

        if event["event_type"] == "EVIDENCE_RESTORED":
            return "ACTIVE"

    return "ACTIVE"



def _draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.rect(0, height - 17 * mm, width, 17 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#34D399"))
    canvas.setFont("CAMGOZ-Bold", 10)
    canvas.drawString(18 * mm, height - 11 * mm, "CAMGOZ")
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("CAMGOZ", 8)
    canvas.drawRightString(width - 18 * mm, 11 * mm, f"CAMGOZ Forensic Report  |  Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#D8E1EA"))
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.restoreState()


def generate_evidence_report(evidence_id: int, output_path: str) -> str:
    """
    Generate a PDF report for one evidence record.
    The original evidence file and database records are not modified.
    """
    regular_font, bold_font = _register_fonts()

    with SessionLocal() as session:
        evidence = session.get(Evidence, evidence_id)
        if evidence is None:
            raise ValueError("Delil kaydı bulunamadı.")

        events = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.evidence_id == evidence_id)
            .order_by(AuditEvent.id.asc())
        ).all()

        # Copy ORM values while the session is open.
        evidence_data = {
            "id": evidence.id,
            "file_name": evidence.file_name,
            "file_path": evidence.file_path,
            "file_size": evidence.file_size,
            "file_type": evidence.file_type,
            "extension": evidence.extension,
            "md5": evidence.md5,
            "sha256": evidence.sha256,
            "created_at": evidence.created_at,
            "modified_at": evidence.modified_at,
            "accessed_at": evidence.accessed_at,
            "analyzed_at": evidence.analyzed_at,
            "notes": evidence.notes,
        }
        event_data = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "event_time": event.event_time,
                "details": event.details,
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
            }
            for event in events
        ]

    integrity_status, integrity_event = _latest_status(event_data)
    archive_status = _archive_status(event_data)
    chain_result = verify_audit_chain()
    generated_at = datetime.now(timezone.utc).isoformat()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CAMTitle", parent=styles["Title"],
        fontName=bold_font, fontSize=21, leading=26,
        textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER,
        spaceAfter=5 * mm
    ))
    styles.add(ParagraphStyle(
        name="CAMSubtitle", parent=styles["Normal"],
        fontName=regular_font, fontSize=9, leading=13,
        textColor=colors.HexColor("#64748B"), alignment=TA_CENTER,
        spaceAfter=8 * mm
    ))
    styles.add(ParagraphStyle(
        name="CAMHeading", parent=styles["Heading2"],
        fontName=bold_font, fontSize=12, leading=16,
        textColor=colors.HexColor("#047857"),
        spaceBefore=5 * mm, spaceAfter=2 * mm
    ))
    styles.add(ParagraphStyle(
        name="CAMBody", parent=styles["BodyText"],
        fontName=regular_font, fontSize=8, leading=11,
        wordWrap="CJK"
    ))
    styles.add(ParagraphStyle(
        name="CAMSmall", parent=styles["BodyText"],
        fontName=regular_font, fontSize=7, leading=9,
        wordWrap="CJK"
    ))

    story = [
        Spacer(1, 8 * mm),
        Paragraph("DIGITAL FORENSIC REPORT", styles["CAMTitle"]),
        Paragraph("CAMGOZ • Evidence Examination Record", styles["CAMSubtitle"]),
    ]

    def add_section(title, rows):
        story.append(Paragraph(title, styles["CAMHeading"]))
        table_data = []
        for label, value in rows:
            table_data.append([
                Paragraph(f"<b>{_safe(label)}</b>", styles["CAMBody"]),
                Paragraph(_safe(value), styles["CAMBody"])
            ])
        table = Table(table_data, colWidths=[48 * mm, 125 * mm], repeatRows=0)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1E293B")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)

    add_section("1. REPORT INFORMATION", [
        ("Report generated (UTC)", generated_at),
        ("Evidence ID", evidence_data["id"]),
        ("Report scope", "Single evidence record and its recorded audit history"),
    ])

    add_section("2. EVIDENCE IDENTIFICATION", [
        ("File name", evidence_data["file_name"]),
        ("Original path", evidence_data["file_path"]),
        ("File size", _format_size(evidence_data["file_size"])),
        ("Detected type", evidence_data["file_type"]),
        ("Extension", evidence_data["extension"]),
        ("Notes", evidence_data["notes"]),
    ])

    add_section("3. CRYPTOGRAPHIC HASHES", [
        ("MD5", evidence_data["md5"]),
        ("SHA-256", evidence_data["sha256"]),
    ])

    add_section("4. FILE TIMESTAMPS", [
        ("Created (UTC)", evidence_data["created_at"]),
        ("Modified (UTC)", evidence_data["modified_at"]),
        ("Accessed (UTC)", evidence_data["accessed_at"]),
        ("Analyzed (UTC)", evidence_data["analyzed_at"]),
    ])

    integrity_labels = {
        "INTEGRITY_VERIFIED": "VERIFIED - latest recorded check matched SHA-256",
        "INTEGRITY_FAILED": "FAILED - latest recorded check did not match SHA-256",
        "FILE_MISSING": "FILE MISSING - latest recorded check could not find file",
        "NOT_CHECKED": "NOT CHECKED - no integrity check is recorded",
    }
    integrity_text = integrity_labels.get(
        integrity_status, f"UNKNOWN - {integrity_status}"
    )
    add_section("5. INTEGRITY STATUS", [
        ("Latest recorded status", integrity_text),
        ("Check event ID", integrity_event["id"] if integrity_event else "-"),
        ("Check timestamp", integrity_event["event_time"] if integrity_event else "-"),
        ("Important", "This is the latest recorded check, not a live verification performed while generating this report."),
    ])

    add_section("6. EVIDENCE LIFECYCLE", [
        ("Current application status", archive_status),
        ("Meaning", "Archived records remain in the database; archive/restore does not delete or move the original file."),
    ])

    add_section("7. GLOBAL AUDIT CHAIN", [
        ("Chain validation", "VALID" if chain_result.get("valid") else "INVALID"),
        ("Total audit events", chain_result.get("total_events", "-")),
        ("Last chain hash", chain_result.get("last_hash", "-")),
        ("Invalid event ID", chain_result.get("event_id", "-")),
        ("Validation reason", chain_result.get("reason", "-")),
    ])

    story.append(Paragraph("8. EVIDENCE AUDIT HISTORY", styles["CAMHeading"]))
    if not event_data:
        story.append(Paragraph("No audit events are recorded for this evidence.", styles["CAMBody"]))
    else:
        audit_rows = [[
            Paragraph("<b>ID</b>", styles["CAMSmall"]),
            Paragraph("<b>EVENT</b>", styles["CAMSmall"]),
            Paragraph("<b>ACTOR</b>", styles["CAMSmall"]),
            Paragraph("<b>TIME (UTC)</b>", styles["CAMSmall"]),
            Paragraph("<b>DETAILS</b>", styles["CAMSmall"]),
        ]]
        for event in event_data:
            try:
                details = json.dumps(
                    json.loads(event["details"] or "{}"),
                    ensure_ascii=False
                )
            except (ValueError, TypeError):
                details = event["details"] or ""
            audit_rows.append([
                Paragraph(_safe(event["id"]), styles["CAMSmall"]),
                Paragraph(_safe(event["event_type"]), styles["CAMSmall"]),
                Paragraph(_safe(event["actor"]), styles["CAMSmall"]),
                Paragraph(_safe(event["event_time"]), styles["CAMSmall"]),
                Paragraph(_safe(details), styles["CAMSmall"]),
            ])

        audit_table = Table(
            audit_rows,
            colWidths=[10 * mm, 32 * mm, 25 * mm, 35 * mm, 71 * mm],
            repeatRows=1
        )
        audit_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white, colors.HexColor("#F8FAFC")
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(audit_table)

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "This report reflects information stored in CAMGOZ at the time of report generation. "
        "It does not independently certify the authenticity or legal admissibility of the evidence.",
        styles["CAMSmall"]
    ))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=24 * mm, bottomMargin=22 * mm,
        title=f"CAMGOZ Forensic Report - Evidence {evidence_id}",
        author="CAMGOZ"
    )
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return str(output.resolve())
