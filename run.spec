# -*- mode: python -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=['D:\\jcc\\AntBrick'],
             binaries=[],
            datas=[('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\brickTrade\\*.json','vnpy\\trader\\app\\brickTrade'),
                ('D:\\jcc\\AntBrick\\vnpy\\trader\*.json','vnpy\\trader'),
                    ('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\riskManager\\RM_setting.json','vnpy\\trader\\app\\riskManager'),
                    ('D:\\jcc\\AntBrick\\GatewayConfig\\*.json','GatewayConfig'),
                     ('D:\\jcc\\AntBrick\\jingtum_python_lib\\*.json','jingtum_python_lib'),
                 ('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\riskManager\\*.ico','vnpy\\trader\\app\\riskManager'),
                    ('D:\\jcc\\AntBrick\\vnpy\\trader\\ico\\*.ico','vnpy\\trader\\ico'),
                    ('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\algoTrading\\*.ico','vnpy\\trader\\app\\algoTrading')
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
          [],
          exclude_binaries=True,
          name='run',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='CfgData')
