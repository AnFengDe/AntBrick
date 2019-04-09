# -*- mode: python -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=[],
             #binaries=[('C:\\Windows\\SysWOW64\\api-ms-win-crt-runtime-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-heap-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-convert-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-string-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-time-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-utility-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-math-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-stdio-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-environment-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-locale-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-filesystem-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-multibyte-l1-1-0.dll','dll'),
             #('C:\\Windows\SysWOW64\\api-ms-win-crt-filesystem-l1-1-0.dll','dll')],
            datas=[('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\brickTrade\\*.json','vnpy\\trader\\app\\brickTrade'),
                    ('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\riskManager\\RM_setting.json','vnpy\\trader\\app\\riskManager'),
                    ('D:\\jcc\\AntBrick\\GatewayConfig\\*.json','GatewayConfig'),
                 ('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\riskManager\\*.ico','vnpy\\trader\\app\\riskManager'),
                    ('D:\\jcc\\AntBrick\\vnpy\\trader\\ico\\*.ico','vnpy\\trader\\ico')
                ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
        a.scripts,
        a.binaries,
    a.datas,
    a.zipfiles,
        name='AntBrick',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=True)