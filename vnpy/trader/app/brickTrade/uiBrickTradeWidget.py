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

        self.followBtcEngine = followBtcEngine
        self.eventEngine = eventEngine

        self.initUi()
        self.updateEngineStatus()

    # ----------------------------------------------------------------------
    def initUi(self):
        # self.vtSymbolList=settings.keys()
        self.comboVtSymbol = QtWidgets.QComboBox()
        try:
            for key in self.followBtcEngine.settingsDict.keys():
                if '.' in key:
                    self.comboVtSymbol.addItem(key)
        except Exception as e:
            print(e)

        # 报价相关设置
        self.lineSymbolBasicPrice = QtWidgets.QLineEdit()
        self.lineSymbolMinPrice = QtWidgets.QLineEdit()
        self.lineSymbolMaxPrice = QtWidgets.QLineEdit()
        self.lineBtcBasicPrice = QtWidgets.QLineEdit()
        self.lineOrderLevel = QtWidgets.QLineEdit()
        self.lineOrderPriceGap = QtWidgets.QLineEdit()
        self.lineOrderVolumeMin = QtWidgets.QLineEdit()
        self.lineOrderVolumeMax = QtWidgets.QLineEdit()
        self.lineBtcCheckInterval = QtWidgets.QLineEdit()
        self.linePriceRatio = QtWidgets.QLineEdit()

        Label = QtWidgets.QLabel

        gridBtcCheck = QtWidgets.QGridLayout()
        # gridBtcCheck.addWidget(Label(u'交易对代码'), 0, 0)
        # gridBtcCheck.addWidget(self.comboVtSymbol, 0, 1)
        # gridBtcCheck.addWidget(Label(u'交易对基准价'), 1, 0)
        # gridBtcCheck.addWidget(self.lineSymbolBasicPrice, 1, 1)
        # gridBtcCheck.addWidget(Label(u'交易对最低价'), 2, 0)
        # gridBtcCheck.addWidget(self.lineSymbolMinPrice, 2, 1)
        # gridBtcCheck.addWidget(Label(u'交易对最高价'), 3, 0)
        # gridBtcCheck.addWidget(self.lineSymbolMaxPrice, 3, 1)
        # gridBtcCheck.addWidget(Label(u'比特币基准价(USDT)'), 4, 0)
        # gridBtcCheck.addWidget(self.lineBtcBasicPrice, 4, 1)
        # gridBtcCheck.addWidget(Label(u'买卖档数'), 5, 0)
        # gridBtcCheck.addWidget(self.lineOrderLevel, 5, 1)
        # gridBtcCheck.addWidget(Label(u'档间价差倍数'), 6, 0)
        # gridBtcCheck.addWidget(self.lineOrderPriceGap, 6, 1)
        # gridBtcCheck.addWidget(Label(u'每档挂单数量上限'), 7, 0)
        # gridBtcCheck.addWidget(self.lineOrderVolumeMax, 7, 1)
        # gridBtcCheck.addWidget(Label(u'每档挂单数量下限'), 8, 0)
        # gridBtcCheck.addWidget(self.lineOrderVolumeMin, 8, 1)
        # gridBtcCheck.addWidget(Label(u'比特币检查时间间隔(秒)'), 9, 0)
        # gridBtcCheck.addWidget(self.lineBtcCheckInterval, 9, 1)
        # gridBtcCheck.addWidget(Label(u'价格波动倍数'), 10, 0)
        # gridBtcCheck.addWidget(self.linePriceRatio, 10, 1)
        #
        # gridSplit = SplitGrid()
        #
        # # 刷单相关设置
        # gridSelfTrade = QtWidgets.QGridLayout()
        # self.lineSelfTradeVolume = QtWidgets.QLineEdit()
        # self.lineSelfTradeInterval = QtWidgets.QLineEdit()
        # self.lineSelfTradeDayVolume = QtWidgets.QLineEdit()
        #
        # gridSelfTrade.addWidget(Label(u'每次刷单平均数量'), 0, 0)
        # gridSelfTrade.addWidget(self.lineSelfTradeVolume, 0, 1)
        # gridSelfTrade.addWidget(Label(u'刷单间隔时间(秒)'), 1, 0)
        # gridSelfTrade.addWidget(self.lineSelfTradeInterval, 1, 1)
        # gridSelfTrade.addWidget(Label(u'预估每日刷单数量'), 2, 0)
        # gridSelfTrade.addWidget(self.lineSelfTradeDayVolume, 2, 1)
        # self.lineSelfTradeDayVolume.setStyleSheet("color: yellow")
        #
        # self.buttonSaveSetting = QtWidgets.QPushButton(u'保存配置')
        # self.buttonSaveSetting.setStyleSheet("background-color: blue")
        #buttonActivate = QtWidgets.QPushButton(u'激活算法')
        self.buttonSwitchEngineStatus = QtWidgets.QPushButton(u'开始搬砖')

        hbox = QtWidgets.QHBoxLayout()
        hbox.addStretch()
        # hbox.addWidget(self.buttonSaveSetting)
        hbox.addWidget(self.buttonSwitchEngineStatus)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(gridBtcCheck)
        # vbox.addLayout(gridSplit)
        # vbox.addLayout(gridSelfTrade)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.getsettingForVTSymbol()  # 根据vtsymbol读取配置

        # 关联更新
        self.comboVtSymbol.currentIndexChanged.connect(self.getsettingForVTSymbol)
        # self.buttonSaveSetting.clicked.connect(self.saveSettingForVTSymbol)
        self.buttonSwitchEngineStatus.clicked.connect(self.switchEngineStatus)

    def getsettingForVTSymbol(self):
        """根据交易对读取配置信息"""
        self.vtSymbol = str(self.comboVtSymbol.currentText())
        if self.vtSymbol:
            setting = self.followBtcEngine.settingsDict[self.vtSymbol]
        else:
            return

        try:
            self.lineSymbolBasicPrice.setText(str(setting['symbolBasicPrice']))
            self.lineSymbolMinPrice.setText(str(setting['symbolMinPrice']))
            self.lineSymbolMaxPrice.setText(str(setting['symbolMaxPrice']))
            self.lineBtcBasicPrice.setText(str(setting['btcBasicPrice']))
            self.lineOrderLevel.setText(str(setting['orderLevel']))
            self.lineOrderPriceGap.setText(str(setting['orderPriceGap']))
            self.lineOrderVolumeMin.setText(str(setting['orderVolumeMin']))
            self.lineOrderVolumeMax.setText(str(setting['orderVolumeMax']))
            self.lineBtcCheckInterval.setText(str(setting['btcCheckInterval']))
            #self.linePlaceOrderInterval.setText(str(setting['placeOrderInterval']))
            self.lineSelfTradeVolume.setText(str(setting['selfTradeVolume']))
            self.lineSelfTradeInterval.setText(str(setting['selfTradeInterval']))
        except Exception as e:
            print(e)

    def getSettingFromMenu(self):
        # 写入配置到settingsDict
        try:
            setting = self.followBtcEngine.settingsDict[self.vtSymbol]

            setting['symbolBasicPrice'] = float(self.lineSymbolBasicPrice.text())
            setting['symbolMinPrice'] = float(self.lineSymbolMinPrice.text())
            setting['symbolMaxPrice'] = float(self.lineSymbolMaxPrice.text())
            setting['btcBasicPrice'] = float(self.lineBtcBasicPrice.text())
            setting['orderLevel'] = int(self.lineOrderLevel.text())
            setting['orderPriceGap'] = float(self.lineOrderPriceGap.text())
            setting['orderVolumeMin'] = float(self.lineOrderVolumeMin.text())
            setting['orderVolumeMax'] = float(self.lineOrderVolumeMax.text())
            setting['btcCheckInterval'] = float(self.lineBtcCheckInterval.text())
            setting['selfTradeVolume'] = float(self.lineSelfTradeVolume.text())
            setting['selfTradeInterval'] = float(self.lineSelfTradeInterval.text())
        except Exception as e:
            print(e)

    def saveSettingForVTSymbol(self):
        self.getSettingFromMenu()
        self.followBtcEngine.saveSetting()

    def switchEngineStatus(self):
        self.followBtcEngine.switchEngineStatus()
        self.updateEngineStatus()

    def updateEngineStatus(self):
        """更新引擎状态"""
        if self.followBtcEngine.active:
            self.buttonSwitchEngineStatus.setText(u'运行中')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: green")
        else:
            self.buttonSwitchEngineStatus.setText(u'开始搬砖')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: gray")
