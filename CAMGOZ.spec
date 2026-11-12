
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

project_dir = Path(SPECPATH)

hidden_imports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtPrintSupport",
    "sqlalchemy",
    "reportlab",
    "watchdog",
    "pylnk3",
]

hidden_imports += collect_submodules("modules")
hidden_imports += collect_submodules("core")
hidden_imports += collect_submodules("ui")
hidden_imports += collect_submodules("database")

datas = [
    (str(project_dir / "assets" / "CAMGOZ.ico"), "assets"),
    (str(project_dir / "assets" / "CAMGOZ_logo.png"), "assets"),
]

datas += collect_data_files("reportlab")

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "tests",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CAMGOZ",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_dir / "assets" / "CAMGOZ.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CAMGOZ",
)
