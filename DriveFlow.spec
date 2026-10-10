# -*- mode: python ; coding: utf-8 -*-
import os
import runpy
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
version = runpy.run_path('driveflow/version.py')['__version__']
numbers = tuple(int(x) for x in version.split('.')) + (0,)
portable = os.environ.get('DRIVEFLOW_ONEFILE') == '1'
version_info = VSVersionInfo(ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription', 'DriveFlow'), StringStruct('FileVersion', version), StringStruct('ProductName', 'DriveFlow'), StringStruct('ProductVersion', version)])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
# Optional Desktop OAuth client (never committed): enables "Entrar com Google".
oauth_client = [('driveflow/oauth_client.json', 'driveflow')] if os.path.exists('driveflow/oauth_client.json') else []
a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('driveflow/update_helper.ps1', 'driveflow'), ('upload.png', '.'), ('upload.ico', '.'), ('transferencias_24px.png', '.'),
           ('historico_24px.png', '.'), ('config_24px.png', '.'), ('lista_24px.png', '.'),
           ('graficos.svg', '.'), ('check.svg', '.'), ('chevron.svg', '.'), ('play_24px.png', '.'),
           ('pausa_24px.png', '.'), ('stop.png', '.'), ('remover.png', '.')] + oauth_client,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 on Windows imports the operating system's ICU shim. A different ICU
# with the same filename can be found on PATH (e.g. Poppler) during analysis.
# Do not bundle that incompatible library; let the Windows loader use System32.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() not in {'icuuc.dll', 'icuin.dll', 'icudt.dll'}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries if portable else [],
    a.datas if portable else [],
    exclude_binaries=not portable,
    name=f'DriveFlow-v{version}-portatil' if portable else 'DriveFlow',
    version=version_info,
    icon='upload.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if not portable:
    coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DriveFlow',
    )
