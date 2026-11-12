
import os
from pathlib import Path
from datetime import datetime
from typing import Any

import pylnk3


def _safe_get(obj: Any, *attributes: str) -> Any:
    """Nesneden güvenli şekilde özellik okumayı dener."""
    current = obj

    for attribute in attributes:
        if current is None:
            return None

        try:
            current = getattr(current, attribute, None)
        except Exception:
            return None

    return current


def _format_timestamp(timestamp: float | None) -> str | None:
    """Unix zamanını okunabilir tarihe dönüştürür."""
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return None


def _extract_target_path(lnk: Any) -> str | None:
    """LNK içerisindeki hedef dosya yolunu bulmaya çalışır."""

    link_info = _safe_get(lnk, "link_info")

    base_path = _safe_get(link_info, "local_base_path")
    suffix = _safe_get(link_info, "common_path_suffix")

    if base_path and suffix:
        base = str(base_path).rstrip("\\/")
        suffix = str(suffix).lstrip("\\/")
        return str(Path(base) / suffix)

    if base_path:
        return str(base_path)

    if suffix:
        return str(suffix)

    network_info = _safe_get(
        link_info,
        "network_share_info"
    )

    network_name = _safe_get(network_info, "net_name")

    if network_name and suffix:
        return str(network_name).rstrip("\\") + "\\" + str(suffix).lstrip("\\")

    relative_path = _safe_get(lnk, "relative_path")

    if relative_path:
        return str(relative_path)

    path = _safe_get(lnk, "path")

    if path:
        return str(path)

    return None


def _get_shortcut_metadata(shortcut: Path) -> dict:
    """Kısayol dosyasının kendi dosya sistemi bilgilerini alır."""

    try:
        stat = shortcut.stat()

        return {
            "shortcut_created_at": _format_timestamp(stat.st_ctime),
            "shortcut_modified_at": _format_timestamp(stat.st_mtime),
            "shortcut_accessed_at": _format_timestamp(stat.st_atime),
        }

    except OSError:
        return {
            "shortcut_created_at": None,
            "shortcut_modified_at": None,
            "shortcut_accessed_at": None,
        }


def collect_recent_files(
    recent_dir: str | Path | None = None,
    max_results: int = 500
) -> list[dict]:
    """
    Windows Recent klasöründeki LNK kısayollarını analiz eder.

    Args:
        recent_dir: Test veya özel kullanım için alternatif klasör.
        max_results: En fazla okunacak kısayol sayısı.

    Returns:
        Analiz sonuçlarını içeren sözlük listesi.
    """

    if recent_dir is None:
        appdata = os.environ.get("APPDATA")

        if not appdata:
            raise EnvironmentError(
                "APPDATA ortam değişkeni bulunamadı."
            )

        recent_dir = (
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Recent"
        )

    recent_path = Path(recent_dir)

    if not recent_path.exists():
        raise FileNotFoundError(
            f"Recent klasörü bulunamadı: {recent_path}"
        )

    if not recent_path.is_dir():
        raise NotADirectoryError(
            f"Belirtilen yol bir klasör değil: {recent_path}"
        )

    shortcuts = list(recent_path.glob("*.lnk"))

    shortcuts.sort(
        key=lambda item: item.stat().st_mtime,
        reverse=True
    )

    results = []

    for shortcut in shortcuts[:max_results]:
        metadata = _get_shortcut_metadata(shortcut)

        record = {
            "shortcut_name": shortcut.name,
            "shortcut_path": str(shortcut),
            "target_path": None,
            "description": None,
            "arguments": None,
            "working_directory": None,
            **metadata,
            "parse_status": "failed",
            "error": None,
        }

        try:
            lnk = pylnk3.parse(str(shortcut))

            record["target_path"] = _extract_target_path(lnk)
            record["description"] = _safe_get(lnk, "description")
            record["arguments"] = _safe_get(lnk, "arguments")
            record["working_directory"] = _safe_get(
                lnk,
                "working_dir"
            )

            record["parse_status"] = "success"

        except Exception as exc:
            record["error"] = str(exc)

        results.append(record)

    return results
