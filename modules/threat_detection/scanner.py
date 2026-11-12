from pathlib import Path
import hashlib

HIGH = {".exe", ".dll", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse", ".wsf", ".hta", ".msi", ".reg"}
MEDIUM = {".jar", ".py", ".pyw", ".sh", ".psm1", ".7z", ".rar", ".iso"}
EXPECTED = {
    ".exe": "PE executable", ".dll": "PE executable", ".scr": "PE executable",
    ".pdf": "PDF document", ".png": "PNG image", ".jpg": "JPEG image",
    ".jpeg": "JPEG image", ".zip": "ZIP archive", ".docx": "ZIP archive",
    ".xlsx": "ZIP archive", ".pptx": "ZIP archive", ".gif": "GIF image",
}
SIGNATURES = [
    (b"MZ", "PE executable"), (b"%PDF-", "PDF document"),
    (b"\x89PNG\r\n\x1a\n", "PNG image"), (b"\xff\xd8\xff", "JPEG image"),
    (b"PK\x03\x04", "ZIP archive"), (b"GIF87a", "GIF image"),
    (b"GIF89a", "GIF image"),
]
WORDS = ("crack", "keygen", "patcher", "activator", "stealer", "password", "urgent", "free")


def _hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze_file(file_path):
    p = Path(file_path)
    try:
        if not p.is_file():
            raise ValueError("Not a regular file")
        stat = p.stat()
        with p.open("rb") as f:
            header = f.read(16)
        signature = next((label for sig, label in SIGNATURES if header.startswith(sig)), "Unknown")
        ext = p.suffix.lower()
        score, reasons = 0, []
        if ext in HIGH:
            score += 45
            reasons.append(f"Executable/script-capable extension: {ext}")
        elif ext in MEDIUM:
            score += 20
            reasons.append(f"Potentially executable/archive extension: {ext}")
        if ext in EXPECTED and signature != EXPECTED[ext]:
            score += 45
            reasons.append(f"Extension/signature mismatch: expected {EXPECTED[ext]}, found {signature}")
        suffixes = [s.lower() for s in p.suffixes]
        disguises = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".txt"}
        if len(suffixes) > 1 and suffixes[-2] in disguises and suffixes[-1] in HIGH:
            score += 35
            reasons.append("Double extension may disguise an executable/script")
        hits = [w for w in WORDS if w in p.name.casefold()]
        if hits:
            score += 10
            reasons.append("Suspicious filename keyword(s): " + ", ".join(hits))
        score = min(score, 100)
        risk = "CRITICAL" if score >= 70 else "HIGH" if score >= 45 else "MEDIUM" if score >= 20 else "LOW"
        return {
            "path": str(p.resolve()), "name": p.name, "extension": ext or "(none)",
            "size": stat.st_size, "sha256": _hash(p), "signature": signature,
            "risk": risk, "score": score,
            "reasons": reasons or ["No configured heuristic indicator detected"],
            "status": "ANALYZED",
        }
    except Exception as exc:
        return {"path": str(p), "name": p.name, "extension": p.suffix.lower(),
                "size": 0, "sha256": "", "signature": "Unavailable", "risk": "ERROR",
                "score": 0, "reasons": [str(exc)], "status": "ERROR"}


def scan_path(target, recursive=True, max_files=5000):
    p = Path(target)
    if p.is_file():
        return [analyze_file(p)], 0
    if not p.is_dir():
        raise FileNotFoundError(str(p))
    iterator = p.rglob("*") if recursive else p.iterdir()
    results, skipped = [], 0
    for item in iterator:
        try:
            if item.is_file():
                if len(results) >= max_files:
                    skipped += 1
                    break
                results.append(analyze_file(item))
        except OSError:
            skipped += 1
    return results, skipped
