# -*- mode: python ; coding: utf-8 -*-
#
# Arquivo: LogFacil.spec
# Descrição: Arquivo de especificação para compilação (build) com PyInstaller.
# Contém as configurações essenciais (hiddenimports, opções uac_admin, etc) para gerar 
# o executável nativo Windows da aplicação.


block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['customtkinter', 'requests', 'Pillow', 'xml.etree.ElementTree', 'unicodedata'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LogFacil',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Oculta a janela preta
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True, # Força execução como administrador (pede permissão no EXE automaticamente) 
)
