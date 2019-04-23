# encoding: UTF-8

'''
跟随BTC模块相关的GUI控制组件
'''

from vnpy.trader.uiBasicWidget import QtWidgets


class HorizonSplitLine(QtWidgets.QFrame):
    # 水平分割线
    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        super().__init__()
        self.setFrameShape(self.HLine)
        self.setFrameShadow(self.Sunken)
        self.setStyleSheet("background-color: blue")


class SplitGrid(QtWidgets.QFormLayout):
    # 水平分割线
    def __init__(self):
        """Constructor"""
        super().__init__()
        lineSplit = HorizonSplitLine()
        self.addWidget(lineSplit)


########################################################################
class BrickTradeManager(QtWidgets.QWidget):
    """跟随BTC引擎的管理组件"""
    #----------------------------------------------------------------------
    def __init__(self, followBtcEngine, eventEngine, parent=None):
        """Constructor"""
        super().__init__(parent)

        self.brickEngine = followBtcEngine
        self.eventEngine = eventEngine

        self.initUi()
        self.updateEngineStatus()

    # ----------------------------------------------------------------------
    def initUi(self):
        # self.vtSymbolList=settings.keys()
        self.comboVtSymbol = QtWidgets.QComboBox()
        try:
            for key in self.brickEngine.settingsDict.keys():
                if '.' in key:
                    self.comboVtSymbol.addItem(key)
        except Exception as e:
            print(e)

        # 报价相关设置
        self.lineGapLimit = QtWidgets.QLineEdit()
        self.lineUsdtCnyRate = QtWidgets.QLineEdit()
        self.lineAmount = QtWidgets.QLineEdit()

        Label = QtWidgets.QLabel

        gridBtcCheck = QtWidgets.QGridLayout()
        gridBtcCheck.addWidget(Label(u'可接受价差(%)'), 0, 0)
        gridBtcCheck.addWidget(self.lineGapLimit, 0, 1)
        gridBtcCheck.addWidget(Label(u'CNY/USDT汇率'), 1, 0)
        gridBtcCheck.addWidget(self.lineUsdtCnyRate, 1, 1)
        gridBtcCheck.addWidget(Label(u'单笔挂单金额'), 2, 0)
        gridBtcCheck.addWidget(self.lineAmount, 2, 1)
        #
        self.buttonSaveSetting = QtWidgets.QPushButton(u'保存配置')
        self.buttonSaveSetting.setStyleSheet("background-color: blue")
        self.buttonCancelAll = QtWidgets.QPushButton(u'全部撤单')
        self.buttonSwitchEngineStatus = QtWidgets.QPushButton(u'开始搬砖')

        hbox = QtWidgets.QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self.buttonSaveSetting)
        hbox.addWidget(self.buttonCancelAll)
        hbox.addWidget(self.buttonSwitchEngineStatus)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(gridBtcCheck)
        # vbox.addLayout(gridSplit)
        # vbox.addLayout(gridSelfTrade)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.getSetting()  # 根据vtsymbol读取配置

        # 关联更新
        self.comboVtSymbol.currentIndexChanged.connect(self.getSetting)
        self.buttonSaveSetting.clicked.connect(self.saveSetting)
        self.buttonCancelAll.clicked.connect(self.cancelAll)
        self.buttonSwitchEngineStatus.clicked.connect(self.switchEngineStatus)

    def getSetting(self):
        """读取配置信息"""
        setting = self.brickEngine.settingsDict

        try:
            self.lineGapLimit.setText(str(float(setting['gapLimit']) * 100))
            self.lineUsdtCnyRate.setText(str(setting['exchangeRate']['CNY_USD']))
            self.lineAmount.setText(str(setting['amount']))
        except Exception as e:
            print(e)

    def getSettingFromMenu(self):
        # 写入配置到settingsDict
        try:
            setting = self.brickEngine.settingsDict
            setting['gapLimit'] = float(self.lineGapLimit.text()) / 100
            setting['exchangeRate']['CNY_USD'] = float(self.lineUsdtCnyRate.text())
            setting['amount'] = float(self.lineAmount.text())
        except Exception as e:
            print(e)

    def saveSetting(self):
        self.getSettingFromMenu()
        self.brickEngine.saveSetting()

    def cancelAll(self):
        self.brickEngine.cancelAll()

    def switchEngineStatus(self):
        self.brickEngine.switchEngineStatus()
        self.updateEngineStatus()

    def updateEngineStatus(self):
        """更新引擎状态"""
        if self.brickEngine.active:
            self.buttonSwitchEngineStatus.setText(u'运行中')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: green")
        else:
            self.buttonSwitchEngineStatus.setText(u'开始搬砖')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: gray")
