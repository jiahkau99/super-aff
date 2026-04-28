# PyInstaller spec for the super-aff FastAPI backend sidecar.
#
# Build with:
#   uv run pyinstaller pyinstaller.spec --noconfirm --clean
#
# Output: dist/super-aff-backend(.exe) — a single-file binary the Tauri shell
# launches as a sidecar.

# ruff: noqa
# mypy: ignore-errors

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = []
binaries = []
hiddenimports = []

# imageio-ffmpeg bundles the ffmpeg binary inside its package; collect it.
ff_datas, ff_binaries, ff_hidden = collect_all("imageio_ffmpeg")
datas += ff_datas
binaries += ff_binaries
hiddenimports += ff_hidden

# uvicorn picks workers/loops/HTTP impls dynamically — pin them.
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

# FastAPI / pydantic edge cases.
datas += collect_data_files("fastapi")

block_cipher = None

a = Analysis(
    ["run_server.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="super-aff-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
