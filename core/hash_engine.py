import hashlib
from pathlib import Path


def calculate_file_hashes(file_path: str) -> dict:
    """
    Calculates MD5 and SHA256 hashes without modifying
    the original evidence file.
    """

    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            md5.update(chunk)
            sha256.update(chunk)

    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest()
    }


def verify_file_integrity(file_path: str, original_sha256: str) -> bool:
    """
    Checks whether a file still matches its original SHA256.
    """

    current_hashes = calculate_file_hashes(file_path)

    return current_hashes["sha256"].lower() == original_sha256.lower()
