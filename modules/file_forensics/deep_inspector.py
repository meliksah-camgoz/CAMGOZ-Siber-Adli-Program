
import mimetypes
from pathlib import Path


# Known file signatures and their expected extensions.
FILE_SIGNATURES = [
    {
        "name": "Windows Executable (PE)",
        "signature": b"\x4D\x5A",
        "extensions": [".exe", ".dll", ".sys", ".scr"],
        "offset": 0,
    },
    {
        "name": "Linux Executable (ELF)",
        "signature": b"\x7FELF",
        "extensions": [".elf", ".so", ""],
        "offset": 0,
    },
    {
        "name": "PNG Image",
        "signature": b"\x89PNG\r\n\x1a\n",
        "extensions": [".png"],
        "offset": 0,
    },
    {
        "name": "JPEG Image",
        "signature": b"\xFF\xD8\xFF",
        "extensions": [".jpg", ".jpeg"],
        "offset": 0,
    },
    {
        "name": "GIF Image",
        "signature": b"GIF87a",
        "extensions": [".gif"],
        "offset": 0,
    },
    {
        "name": "GIF Image",
        "signature": b"GIF89a",
        "extensions": [".gif"],
        "offset": 0,
    },
    {
        "name": "PDF Document",
        "signature": b"%PDF-",
        "extensions": [".pdf"],
        "offset": 0,
    },
    {
        "name": "ZIP Archive",
        "signature": b"PK\x03\x04",
        "extensions": [".zip", ".docx", ".xlsx", ".pptx", ".jar", ".apk"],
        "offset": 0,
    },
    {
        "name": "SQLite Database",
        "signature": b"SQLite format 3\x00",
        "extensions": [".db", ".sqlite", ".sqlite3"],
        "offset": 0,
    },
    {
        "name": "RAR Archive",
        "signature": b"Rar!\x1A\x07",
        "extensions": [".rar"],
        "offset": 0,
    },
    {
        "name": "GZIP Archive",
        "signature": b"\x1F\x8B",
        "extensions": [".gz", ".gzip"],
        "offset": 0,
    },
    {
        "name": "7-Zip Archive",
        "signature": b"7z\xBC\xAF\x27\x1C",
        "extensions": [".7z"],
        "offset": 0,
    },
    {
        "name": "Windows Shortcut",
        "signature": b"\x4C\x00\x00\x00\x01\x14\x02\x00",
        "extensions": [".lnk"],
        "offset": 0,
    },
    {
        "name": "OLE Compound Document",
        "signature": b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        "extensions": [".doc", ".xls", ".ppt", ".msi"],
        "offset": 0,
    },
]


def detect_signature(file_path: str) -> dict:
    """
    Detect the actual file signature from its header.
    The original file is only read, never modified.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_symlink():
        raise ValueError("Symbolic links are not accepted.")

    with path.open("rb") as file:
        header = file.read(64)

    for item in FILE_SIGNATURES:
        signature = item["signature"]
        offset = item["offset"]

        if header[offset:offset + len(signature)] == signature:
            return {
                "detected": True,
                "file_type": item["name"],
                "signature_hex": signature.hex(" ").upper(),
                "expected_extensions": item["extensions"],
                "offset": offset,
            }

    mime_type, _ = mimetypes.guess_type(path.name)

    return {
        "detected": False,
        "file_type": "Unknown / Unidentified",
        "signature_hex": header[:16].hex(" ").upper(),
        "expected_extensions": [],
        "mime_type": mime_type,
        "offset": None,
    }


def analyze_signature_mismatch(file_path: str) -> dict:
    """
    Compare the detected file signature with its extension.
    """
    path = Path(file_path)
    result = detect_signature(file_path)

    extension = path.suffix.lower()

    if not result["detected"]:
        result.update({
            "extension": extension or "No extension",
            "mismatch": None,
            "risk": "UNKNOWN",
            "message": "File type could not be identified reliably.",
        })
        return result

    expected = result["expected_extensions"]

    if extension in expected:
        mismatch = False
        risk = "LOW"
        message = "File signature matches its extension."

    else:
        mismatch = True
        risk = "WARNING"
        message = (
            "Detected file signature does not match "
            "the file extension."
        )

    result.update({
        "extension": extension or "No extension",
        "mismatch": mismatch,
        "risk": risk,
        "message": message,
    })

    return result


def create_hex_dump(
    file_path: str,
    offset: int = 0,
    length: int = 256,
    bytes_per_row: int = 16,
) -> list[dict]:
    """
    Generate a hexadecimal and ASCII representation of file bytes.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_symlink():
        raise ValueError("Symbolic links are not accepted.")

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    if length < 1 or length > 1024 * 1024:
        raise ValueError("Length must be between 1 byte and 1 MB.")

    if bytes_per_row < 1 or bytes_per_row > 32:
        raise ValueError("Bytes per row must be between 1 and 32.")

    rows = []

    with path.open("rb") as file:
        file.seek(offset)
        data = file.read(length)

    for index in range(0, len(data), bytes_per_row):
        chunk = data[index:index + bytes_per_row]

        hex_values = " ".join(
            f"{byte:02X}" for byte in chunk
        )

        ascii_values = "".join(
            chr(byte) if 32 <= byte <= 126 else "."
            for byte in chunk
        )

        rows.append({
            "offset": offset + index,
            "hex": hex_values,
            "ascii": ascii_values,
        })

    return rows


def get_file_size(file_path: str) -> int:
    return Path(file_path).stat().st_size


def scan_embedded_signatures(
    file_path: str,
    chunk_size: int = 1024 * 1024,
    max_results: int = 500,
) -> list[dict]:
    """
    Scan a file for known signatures at non-zero offsets.

    The original file is opened read-only.
    Results are limited to prevent excessive memory usage.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_symlink():
        raise ValueError("Symbolic links are not accepted.")

    if chunk_size < 1024:
        raise ValueError("Chunk size must be at least 1024 bytes.")

    if max_results < 1:
        raise ValueError("Maximum results must be positive.")

    # Longer signatures are checked first.
    signatures = sorted(
        FILE_SIGNATURES,
        key=lambda item: len(item["signature"]),
        reverse=True,
    )

    max_signature_length = max(
        len(item["signature"]) for item in signatures
    )

    results = []
    seen = set()

    overlap = max_signature_length - 1
    absolute_offset = 0
    previous_tail = b""

    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)

            if not chunk:
                break

            data = previous_tail + chunk
            data_start = absolute_offset - len(previous_tail)

            for item in signatures:
                signature = item["signature"]
                search_from = 0

                while True:
                    position = data.find(signature, search_from)

                    if position == -1:
                        break

                    actual_offset = data_start + position

                    # Ignore the primary file signature.
                    if actual_offset > 0:
                        key = (item["name"], actual_offset)

                        if key not in seen:
                            seen.add(key)

                            results.append({
                                "file_type": item["name"],
                                "offset": actual_offset,
                                "signature_hex": signature.hex(" ").upper(),
                                "expected_extensions": item["extensions"],
                            })

                            if len(results) >= max_results:
                                return results

                    search_from = position + 1

            absolute_offset += len(chunk)
            previous_tail = data[-overlap:] if overlap else b""

    return results

def search_hex_pattern(
    file_path: str,
    pattern: str,
    max_results: int = 1000,
) -> list[int]:
    """
    Search for a hexadecimal byte pattern in a file.
    Returns the absolute byte offsets of matches.
    """
    from pathlib import Path

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.is_symlink():
        raise ValueError("Symbolic links are not accepted.")

    try:
        needle = bytes.fromhex(pattern)
    except ValueError as error:
        raise ValueError(
            "Invalid hexadecimal pattern. Example: 50 4B 03 04"
        ) from error

    if not needle:
        raise ValueError("Search pattern cannot be empty.")

    if max_results < 1:
        raise ValueError("Maximum results must be positive.")

    results = []
    overlap = b""
    absolute_offset = 0
    seen = set()

    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            data = overlap + chunk
            data_start = absolute_offset - len(overlap)
            position = 0

            while True:
                position = data.find(needle, position)

                if position == -1:
                    break

                match_offset = data_start + position

                if match_offset not in seen:
                    seen.add(match_offset)
                    results.append(match_offset)

                    if len(results) >= max_results:
                        return results

                position += 1

            absolute_offset += len(chunk)
            overlap = data[-(len(needle) - 1):] if len(needle) > 1 else b""

    return results