import os
import mimetypes

from pathlib import Path
from datetime import datetime, timezone

from core.hash_engine import calculate_file_hashes


def detect_file_type(file_path: str) -> str:
    """
    Detects common file types using file signatures.
    Does not rely only on file extensions.
    """

    signatures = {
        b"\x4D\x5A": "Windows Executable (PE)",
        b"\x7FELF": "Linux Executable (ELF)",
        b"\x89PNG\r\n\x1a\n": "PNG Image",
        b"\xFF\xD8\xFF": "JPEG Image",
        b"GIF87a": "GIF Image",
        b"GIF89a": "GIF Image",
        b"%PDF-": "PDF Document",
        b"PK\x03\x04": "ZIP Archive / Office Document",
        b"SQLite format 3\x00": "SQLite Database",
        b"Rar!\x1A\x07": "RAR Archive",
        b"\x1F\x8B": "GZIP Archive",
    }

    with open(file_path, "rb") as file:
        header = file.read(32)

    for signature, file_type in signatures.items():
        if header.startswith(signature):
            return file_type

    guessed_type, _ = mimetypes.guess_type(file_path)

    if guessed_type:
        return f"Unknown signature (extension MIME: {guessed_type})"

    return "Unknown / Unidentified"


def analyze_file(file_path: str) -> dict:
    """
    Performs basic forensic analysis on a file.
    Original file is opened in read-only binary mode.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_symlink():
        raise ValueError("Symbolic links are not accepted as evidence.")

    stat = path.stat()

    hashes = calculate_file_hashes(str(path))

    result = {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_size": stat.st_size,
        "file_type": detect_file_type(str(path)),
        "extension": path.suffix.lower() or "No extension",
        "created_at": datetime.fromtimestamp(
            stat.st_ctime, tz=timezone.utc
        ).isoformat(),
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "accessed_at": datetime.fromtimestamp(
            stat.st_atime, tz=timezone.utc
        ).isoformat(),
        "md5": hashes["md5"],
        "sha256": hashes["sha256"],
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }

    return result
