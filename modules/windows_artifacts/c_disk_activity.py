"""
CAMGOZ - C: NTFS USN Journal monitor (Stage 2).

- Reads new USN Journal records from C:.
- Builds an in-memory NTFS file-reference map using FSCTL_ENUM_USN_DATA.
- Resolves paths when the file-reference/parent chain is available.
- Keeps an in-memory path cache so deleted/renamed items can often retain
  their previous path during the current CAMGOZ run.
- Reads Windows Recycle Bin $I metadata without modifying it.

Important:
- This is a forensic event collector, not a file-content recovery tool.
- USN Journal records do not always provide a complete path by themselves.
- Files deleted before CAMGOZ starts may not be resolvable if their MFT
  entries are already gone and no earlier cached path exists.
- MFT enumeration can take time on large volumes.
"""

from __future__ import annotations

import ctypes
import os
import struct
import threading
from datetime import datetime
from pathlib import Path
from ctypes import wintypes

from sqlalchemy import select

from database.database import SessionLocal
from database.models import FileSystemActivity


if os.name == "nt":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE

    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
else:
    kernel32 = None


GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FSCTL_ENUM_USN_DATA = 0x000900B3
FSCTL_QUERY_USN_JOURNAL = 0x000900F4
FSCTL_READ_USN_JOURNAL = 0x000900BB

_REASON_NAMES = (
    (0x00000100, "FILE_CREATE"),
    (0x00000200, "FILE_DELETE"),
    (0x00000001, "DATA_OVERWRITE"),
    (0x00000002, "DATA_EXTEND"),
    (0x00000004, "DATA_TRUNCATION"),
    (0x00000010, "NAMED_DATA_OVERWRITE"),
    (0x00000020, "NAMED_DATA_EXTEND"),
    (0x00000040, "NAMED_DATA_TRUNCATION"),
    (0x00001000, "RENAME_OLD_NAME"),
    (0x00002000, "RENAME_NEW_NAME"),
    (0x00008000, "BASIC_INFO_CHANGE"),
    (0x00010000, "HARD_LINK_CHANGE"),
    (0x00020000, "COMPRESSION_CHANGE"),
    (0x00040000, "ENCRYPTION_CHANGE"),
    (0x00080000, "OBJECT_ID_CHANGE"),
    (0x00100000, "REPARSE_POINT_CHANGE"),
    (0x00200000, "STREAM_CHANGE"),
    (0x00400000, "CLOSE"),
)

_FILETIME_EPOCH = 116444736000000000
NTFS_ROOT_FILE_REFERENCE = 5


def _now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _filetime_to_text(value: int) -> str | None:
    if not value:
        return None
    try:
        unix_seconds = (value - _FILETIME_EPOCH) / 10_000_000
        return datetime.fromtimestamp(unix_seconds).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, OSError, OverflowError):
        return None


def _reason_names(reason: int) -> list[str]:
    return [name for flag, name in _REASON_NAMES if reason & flag]


def _classify_event(reason: int) -> str:
    if reason & 0x00000100:
        return "FILE_CREATED"
    if reason & 0x00000200:
        return "FILE_DELETED"
    if reason & 0x00001000:
        return "FILE_RENAME_OLD"
    if reason & 0x00002000:
        return "FILE_RENAMED"
    if reason & (
        0x00000001 | 0x00000002 | 0x00000004 |
        0x00000010 | 0x00000020 | 0x00000040
    ):
        return "FILE_MODIFIED"
    if reason & 0x00008000:
        return "FILE_METADATA_CHANGED"
    return "FILE_SYSTEM_CHANGE"


def _open_volume(volume: str):
    if os.name != "nt":
        raise OSError("NTFS USN Journal monitor yalnızca Windows üzerinde çalışır.")

    path = "\\\\.\\" + volume.rstrip("\\")
    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _device_io_control(handle, control_code: int, input_bytes: bytes, output_size=65536):
    input_buffer = ctypes.create_string_buffer(input_bytes) if input_bytes else None
    output_buffer = ctypes.create_string_buffer(output_size)
    returned = wintypes.DWORD(0)

    ok = kernel32.DeviceIoControl(
        handle,
        control_code,
        input_buffer,
        len(input_bytes),
        output_buffer,
        output_size,
        ctypes.byref(returned),
        None,
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())

    return output_buffer.raw[:returned.value]


def _query_journal(handle) -> dict:
    raw = _device_io_control(handle, FSCTL_QUERY_USN_JOURNAL, b"", 128)
    if len(raw) < 56:
        raise OSError("USN Journal yanıtı beklenen uzunlukta değil.")

    values = struct.unpack_from("<QQQQQQQHH", raw, 0)
    return {
        "journal_id": values[0],
        "first_usn": values[1],
        "next_usn": values[2],
        "lowest_valid_usn": values[3],
        "max_usn": values[4],
    }


def _parse_usn_v2_records(raw: bytes) -> list[dict]:
    """Parse USN_RECORD_V2 records from a DeviceIoControl response."""
    records = []
    offset = 0

    while offset + 60 <= len(raw):
        record_length, major, minor = struct.unpack_from("<IHH", raw, offset)
        if record_length < 60 or offset + record_length > len(raw):
            break

        if major == 2:
            file_ref, parent_ref, usn, timestamp, reason = struct.unpack_from(
                "<QQqqI", raw, offset + 8
            )
            filename_length, filename_offset = struct.unpack_from(
                "<HH", raw, offset + 56
            )
            start = offset + filename_offset
            end = start + filename_length
            filename = ""
            if filename_length and end <= offset + record_length:
                filename = raw[start:end].decode(
                    "utf-16-le", errors="replace"
                )

            records.append({
                "file_ref": str(file_ref),
                "parent_ref": str(parent_ref),
                "usn": str(usn),
                "timestamp": _filetime_to_text(timestamp),
                "reason": reason,
                "filename": filename,
                "major": major,
                "minor": minor,
            })

        offset += record_length

    return records


def _enumerate_mft_name_map(handle, stop_event: threading.Event | None = None):
    """
    Enumerate NTFS file names and parent references.

    Returns: file_reference -> (parent_reference, filename)
    This is a best-effort in-memory index; inaccessible or changing entries
    can be absent.
    """
    name_map: dict[str, tuple[str, str]] = {}
    start_file_reference = 0
    low_usn = 0
    high_usn = 0x7FFFFFFFFFFFFFFF
    request_format = "<Qqq"

    while True:
        if stop_event and stop_event.is_set():
            break

        request = struct.pack(
            request_format, start_file_reference, low_usn, high_usn
        )
        try:
            raw = _device_io_control(
                handle, FSCTL_ENUM_USN_DATA, request, 1024 * 1024
            )
        except OSError:
            # End of enumeration or access boundary.
            break

        if len(raw) < 8:
            break

        next_reference = struct.unpack_from("<Q", raw, 0)[0]
        records = _parse_usn_v2_records(raw[8:])

        for item in records:
            if item["filename"]:
                name_map[item["file_ref"]] = (
                    item["parent_ref"],
                    item["filename"],
                )

        if next_reference <= start_file_reference or not records:
            break

        start_file_reference = next_reference

    return name_map


def _resolve_path(
    file_reference: str,
    name_map: dict[str, tuple[str, str]],
    volume: str,
    fallback_name: str | None = None,
) -> str | None:
    """Resolve a path from the NTFS parent-reference chain."""
    current = str(file_reference)
    parts = []
    seen = set()

    for _ in range(256):
        if current in seen:
            return None
        seen.add(current)

        if current == str(NTFS_ROOT_FILE_REFERENCE):
            break

        entry = name_map.get(current)
        if not entry:
            if not parts and fallback_name:
                parts.append(fallback_name)
                return None
            return None

        parent_reference, name = entry
        if name:
            parts.append(name)
        current = str(parent_reference)
    else:
        return None

    if current != str(NTFS_ROOT_FILE_REFERENCE):
        return None

    return volume.rstrip("\\") + "\\" + "\\".join(reversed(parts))


def _read_journal(handle, start_usn: int, journal_id: int) -> tuple[int, list[dict]]:
    request = struct.pack(
        "<qIIQQQ",
        start_usn,
        0xFFFFFFFF,
        0,
        0,
        0,
        journal_id,
    )
    raw = _device_io_control(
        handle, FSCTL_READ_USN_JOURNAL, request, 1024 * 1024
    )
    if len(raw) < 8:
        return start_usn, []

    next_usn = struct.unpack_from("<q", raw, 0)[0]
    return next_usn, _parse_usn_v2_records(raw[8:])


class CDiskActivityMonitor:
    """Polls C: NTFS USN Journal and stores events in SQLite."""

    def __init__(self, volume: str = "C:", poll_interval: float = 3.0):
        self.volume = volume.upper()
        self.poll_interval = max(0.5, float(poll_interval))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "STOPPED"
        self._last_error: str | None = None
        self._last_usn: int | None = None
        self._name_map: dict[str, tuple[str, str]] = {}
        self._rename_old_paths: dict[str, str] = {}

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_usn(self) -> int | None:
        return self._last_usn

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="CAMGOZ-CDisk-USN",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if not self._thread or not self._thread.is_alive():
            self._status = "STOPPED"

    def _store_event(self, item: dict):
        """Build one ORM row; database writes are batched by _save_records."""
        file_ref = item["file_ref"]
        parent_ref = item["parent_ref"]
        filename = item["filename"]
        reason = item["reason"]

        # USN_REASON_CLOSE is extremely common and usually adds no useful
        # standalone forensic information. Skip CLOSE-only records.
        meaningful_mask = 0x00000100 | 0x00000200 | 0x00000001 | 0x00000002 | 0x00000004 | 0x00000010 | 0x00000020 | 0x00000040 | 0x00001000 | 0x00002000 | 0x00008000 | 0x00010000 | 0x00020000 | 0x00040000 | 0x00080000 | 0x00100000 | 0x00200000
        if not (reason & meaningful_mask):
            return None

        event_type = _classify_event(reason)
        old_path = None

        if event_type == "FILE_RENAME_OLD":
            old_path = _resolve_path(
                file_ref, self._name_map, self.volume, filename
            )
            if old_path:
                self._rename_old_paths[file_ref] = old_path

        if filename and event_type not in ("FILE_RENAME_OLD", "FILE_DELETED"):
            self._name_map[file_ref] = (parent_ref, filename)

        resolved_path = _resolve_path(
            file_ref, self._name_map, self.volume, filename
        )

        if event_type == "FILE_RENAMED":
            old_path = self._rename_old_paths.pop(file_ref, None)

        if event_type == "FILE_DELETED":
            resolved_path = _resolve_path(
                file_ref, self._name_map, self.volume, filename
            )
            self._name_map.pop(file_ref, None)

        names = _reason_names(reason)
        details = (
            f"USN reason: {', '.join(names) or hex(reason)}; "
            f"USN record v{item['major']}.{item['minor']}."
        )
        if not resolved_path:
            details += " Tam yol çözümlenemedi; NTFS referans zinciri eksik."
        if event_type == "FILE_RENAME_OLD":
            details += " Eski ad kaydı; yeni ad kaydı ayrıca gelebilir."

        return FileSystemActivity(
            volume=self.volume,
            event_type=event_type,
            event_time=item["timestamp"] or _now_text(),
            source="USN_JOURNAL",
            file_name=filename or None,
            file_path=resolved_path,
            old_path=old_path,
            file_reference=file_ref,
            parent_reference=parent_ref,
            usn=item["usn"],
            details=details,
        )

    def _save_records(self, records: list[dict]):
        """Process and commit a journal batch once instead of per event."""
        if not records:
            return

        pending = []
        for item in records:
            if self._stop_event.is_set():
                break
            try:
                row = self._store_event(item)
                if row is not None:
                    pending.append(row)
            except Exception as exc:
                self._last_error = f"USN kaydı hazırlanamadı: {exc}"

        if not pending:
            return

        try:
            with SessionLocal() as session:
                session.add_all(pending)
                session.commit()
        except Exception as exc:
            self._last_error = f"USN kayıt grubu veritabanına yazılamadı: {exc}"

    def _run(self):
        if os.name != "nt":
            self._status = "UNSUPPORTED"
            self._last_error = "Windows gereklidir."
            return

        handle = None
        try:
            self._status = "STARTING"
            handle = _open_volume(self.volume)

            self._status = "INDEXING"
            self._name_map = _enumerate_mft_name_map(
                handle, self._stop_event
            )
            if self._stop_event.is_set():
                self._status = "STOPPED"
                return

            journal = _query_journal(handle)
            current_usn = journal["next_usn"]
            journal_id = journal["journal_id"]
            self._last_usn = current_usn
            self._last_error = None
            self._status = "MONITORING"

            while not self._stop_event.is_set():
                try:
                    next_usn, records = _read_journal(
                        handle, current_usn, journal_id
                    )
                    self._save_records(records)

                    if next_usn > current_usn:
                        current_usn = next_usn
                        self._last_usn = current_usn

                    self._stop_event.wait(self.poll_interval)

                except OSError as exc:
                    self._last_error = str(exc)
                    self._status = "ERROR"
                    self._stop_event.wait(self.poll_interval)
                    try:
                        journal = _query_journal(handle)
                        journal_id = journal["journal_id"]
                        current_usn = max(
                            current_usn, journal["lowest_valid_usn"]
                        )
                        self._status = "MONITORING"
                    except OSError:
                        continue

        except Exception as exc:
            self._last_error = str(exc)
            self._status = "ERROR"
        finally:
            if handle not in (None, INVALID_HANDLE_VALUE):
                kernel32.CloseHandle(handle)
            if self._status not in ("ERROR", "UNSUPPORTED"):
                self._status = "STOPPED"


def scan_recycle_bin(volume: str = "C:") -> list[dict]:
    """Read Windows $Recycle.Bin $I metadata files; no filesystem changes."""
    if os.name != "nt":
        raise OSError("Geri Dönüşüm Kutusu analizi yalnızca Windows içindir.")

    recycle_root = os.path.join(volume + os.sep, "$Recycle.Bin")
    results = []
    if not os.path.isdir(recycle_root):
        return results

    for user_folder in os.scandir(recycle_root):
        if not user_folder.is_dir(follow_symlinks=False):
            continue

        try:
            entries = os.scandir(user_folder.path)
        except OSError:
            continue

        with entries:
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if not os.path.basename(entry.name).startswith("$I"):
                    continue

                try:
                    data = Path(entry.path).read_bytes()
                    if len(data) < 24:
                        continue

                    version, original_size, deletion_filetime = struct.unpack_from(
                        "<QQQ", data, 0
                    )

                    if version == 1:
                        original_path = data[24:].decode(
                            "utf-16-le", errors="replace"
                        ).rstrip("\x00")
                    elif version == 2:
                        if len(data) < 28:
                            continue
                        name_length = struct.unpack_from("<I", data, 24)[0]
                        original_path = data[
                            28:28 + (name_length * 2)
                        ].decode("utf-16-le", errors="replace").rstrip("\x00")
                    else:
                        continue

                    results.append({
                        "file_name": os.path.basename(original_path) or entry.name,
                        "original_path": original_path,
                        "file_size": original_size,
                        "deleted_at": _filetime_to_text(deletion_filetime),
                        "metadata_path": entry.path,
                        "version": version,
                    })
                except (OSError, ValueError, struct.error):
                    continue

    results.sort(key=lambda item: item.get("deleted_at") or "", reverse=True)
    return results


def import_recycle_bin_records(volume: str = "C:") -> int:
    """Import current Recycle Bin metadata once; duplicate metadata paths skipped."""
    items = scan_recycle_bin(volume)
    inserted = 0

    with SessionLocal() as session:
        existing = set(session.scalars(
            select(FileSystemActivity.file_path).where(
                FileSystemActivity.source == "RECYCLE_BIN",
                FileSystemActivity.volume == volume.upper(),
            )
        ).all())

        for item in items:
            metadata_path = item["metadata_path"]
            if metadata_path in existing:
                continue

            session.add(FileSystemActivity(
                volume=volume.upper(),
                event_type="FILE_DELETED_TO_RECYCLE_BIN",
                event_time=item["deleted_at"] or _now_text(),
                source="RECYCLE_BIN",
                file_name=item["file_name"],
                file_path=metadata_path,
                old_path=item["original_path"],
                details=(
                    f"Original size: {item['file_size']} bytes; "
                    f"Recycle Bin metadata version: {item['version']}. "
                    "This is metadata evidence, not proof that contents remain recoverable."
                ),
            ))
            existing.add(metadata_path)
            inserted += 1

        session.commit()

    return inserted
