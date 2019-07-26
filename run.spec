# -*- mode: python -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=['E:\\workspace\\gaoshan\\vnpy\\AntBrick'],
             binaries=[],
            datas=[('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\brickTradePassive\\*.json','vnpy\\trader\\app\\brickTradePassive'),
                ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\*.json','vnpy\\trader'),
                    ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\riskManager\\RM_setting.json','vnpy\\trader\\app\\riskManager'),
                     ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\brickTradePositive\\*.json','vnpy\\trader\\app\\brickTradePositive'),
                     ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\brickTradeDepthCopy\\*.json','vnpy\\trader\\app\\brickTradeDepthCopy'),
                     ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\GatewayConfig\\*.json','GatewayConfig'),
                     ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\jingtum_python_lib\\*.json','jingtum_python_lib'),
                 ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\riskManager\\*.ico','vnpy\\trader\\app\\riskManager'),
                    ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\ico\\*.ico','vnpy\\trader\\ico'),
                    ('E:\\workspace\\gaoshan\\vnpy\\AntBrick\\vnpy\\trader\\app\\algoTrading\\*.ico','vnpy\\trader\\app\\algoTrading')
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
