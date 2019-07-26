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
        self.lineJccCntBuyPrice = QtWidgets.QLineEdit()
        self.lineJccCntSellPrice= QtWidgets.QLineEdit()
        self.lineCoinbeneUsdtBuyPrice = QtWidgets.QLineEdit()
        self.lineCoinbeneUsdtSellPrice= QtWidgets.QLineEdit()
        self.lineAmount = QtWidgets.QLineEdit()
        self.lineStep = QtWidgets.QLineEdit()
        self.linePrecision = QtWidgets.QLineEdit()
        self.textProfit = QtWidgets.QLineEdit()
        self.textProfit.setEnabled(False)
        self.brickEngine.registProfitCallback(self.profitCallback)

        Label = QtWidgets.QLabel

        gridBtcCheck = QtWidgets.QGridLayout()
        index = 0
        gridBtcCheck.addWidget(Label(u'可接受价差(%)'), index, 0)
        gridBtcCheck.addWidget(self.lineGapLimit, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'威链CNT买入价'), index, 0)
        gridBtcCheck.addWidget(self.lineJccCntBuyPrice, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'威链CNT卖出价'), index, 0)
        gridBtcCheck.addWidget(self.lineJccCntSellPrice, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'满币USDT买入价'), index, 0)
        gridBtcCheck.addWidget(self.lineCoinbeneUsdtBuyPrice, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'满币USDT卖出价'), index, 0)
        gridBtcCheck.addWidget(self.lineCoinbeneUsdtSellPrice, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'单笔挂单金额'), index, 0)
        gridBtcCheck.addWidget(self.lineAmount, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'价差步进量'), index, 0)
        gridBtcCheck.addWidget(self.lineStep, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'价格保留精度'), index, 0)
        gridBtcCheck.addWidget(self.linePrecision, index, 1)
        index += 1
        gridBtcCheck.addWidget(Label(u'持仓收益'), index, 0)
        gridBtcCheck.addWidget(self.textProfit, index, 1)

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

    def profitCallback(self, account_info):
        self.textProfit.setText("Token: %.4f, Cash: %.4f" % (account_info["PROFIT_TOKEN"],account_info["PROFIT_CASH"]))

    def getSetting(self):
        """读取配置信息"""
        setting = self.brickEngine.settingsDict

        try:
            self.lineGapLimit.setText(str(round(float(setting['gapLimit']) * 100, 6)))
            self.lineJccCntBuyPrice.setText(str(setting['otcPrice']['JCC.CNT'][0]))
            self.lineJccCntSellPrice.setText(str(setting['otcPrice']['JCC.CNT'][1]))
            self.lineCoinbeneUsdtBuyPrice.setText(str(setting['otcPrice']['COINBENE.USDT'][0]))
            self.lineCoinbeneUsdtSellPrice.setText(str(setting['otcPrice']['COINBENE.USDT'][1]))
            self.lineAmount.setText(str(setting['amount']))
            self.lineStep.setText(str(setting['step']))
            self.linePrecision.setText(str(setting['precision']))
        except Exception as e:
            print(e)

    def getSettingFromMenu(self):
        # 写入配置到settingsDict
        try:
            setting = self.brickEngine.settingsDict
            setting['gapLimit'] = round(float(self.lineGapLimit.text()) / 100, 8)
            setting['otcPrice']['JCC.CNT'][0] = float(self.lineJccCntBuyPrice.text())
            setting['otcPrice']['JCC.CNT'][1] = float(self.lineJccCntSellPrice.text())
            setting['otcPrice']['COINBENE.USDT'][0] = float(self.lineCoinbeneUsdtBuyPrice.text())
            setting['otcPrice']['COINBENE.USDT'][1] = float(self.lineCoinbeneUsdtSellPrice.text())
            setting['amount'] = float(self.lineAmount.text())
            setting['step'] = float(self.lineStep.text())
            setting['precision'] = int(self.linePrecision.text())
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
