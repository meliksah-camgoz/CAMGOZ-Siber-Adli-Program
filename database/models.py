from sqlalchemy import (
    Integer,
    String,
    BigInteger,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(BigInteger)
    file_type: Mapped[str] = mapped_column(String(200))
    extension: Mapped[str] = mapped_column(String(50))
    md5: Mapped[str] = mapped_column(String(32), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[str] = mapped_column(String(50))
    modified_at: Mapped[str] = mapped_column(String(50))
    accessed_at: Mapped[str] = mapped_column(String(50))
    analyzed_at: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(200))
    event_time: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)


class USBDevice(Base):
    __tablename__ = "usb_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_key: Mapped[str] = mapped_column(String(500), index=True)
    instance_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    hardware_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(300), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_seen_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_seen_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50))


class USBActivity(Base):
    __tablename__ = "usb_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("usb_devices.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    event_time: Mapped[str] = mapped_column(String(50), index=True)
    source: Mapped[str] = mapped_column(String(50))
    drive_letter: Mapped[str | None] = mapped_column(String(10), nullable=True)
    volume_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


Index(
    "ix_usb_activity_device_time",
    USBActivity.device_id,
    USBActivity.event_time,
)
