# encoding: UTF-8

'''
跟随BTC模块相关的GUI控制组件
'''

from vnpy.trader.uiBasicWidget import QtWidgets


#from vnpy.trader.app.alGo.followBtcSelfTrade.language import text

########################################################################
class FollowBtcEngineManager(QtWidgets.QWidget):
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

        # self.lineSymbol = QtWidgets.QLineEdit()
        self.lineSymbolBasicPrice = QtWidgets.QLineEdit()
        self.lineBtcBasicPrice = QtWidgets.QLineEdit()
        self.lineOrderLevel = QtWidgets.QLineEdit()
        self.lineOrderPriceGap = QtWidgets.QLineEdit()
        self.lineOrderVolume = QtWidgets.QLineEdit()
        self.lineBtcCheckInterval = QtWidgets.QLineEdit()
        #self.linePlaceOrderInterval = QtWidgets.QLineEdit()
        self.lineSelfTradeVolume = QtWidgets.QLineEdit()

        self.buttonSaveSetting = QtWidgets.QPushButton(u'保存配置')
        #buttonActivate = QtWidgets.QPushButton(u'激活算法')
        self.buttonSwitchEngineStatus = QtWidgets.QPushButton(u'BTC跟随报价刷单引擎停止')
        Label = QtWidgets.QLabel

        grid = QtWidgets.QGridLayout()
        grid.addWidget(Label(u'交易对代码'), 0, 0)
        grid.addWidget(self.comboVtSymbol, 0, 1)
        grid.addWidget(Label(u'交易对基准价'), 1, 0)
        grid.addWidget(self.lineSymbolBasicPrice, 1, 1)
        grid.addWidget(Label(u'比特币基准价'), 2, 0)
        grid.addWidget(self.lineBtcBasicPrice, 2, 1)
        grid.addWidget(Label(u'买卖档数'), 3, 0)
        grid.addWidget(self.lineOrderLevel, 3, 1)
        grid.addWidget(Label(u'档间价差'), 4, 0)
        grid.addWidget(self.lineOrderPriceGap, 4, 1)
        grid.addWidget(Label(u'每档挂单数量'), 5, 0)
        grid.addWidget(self.lineOrderVolume, 5, 1)
        grid.addWidget(Label(u'比特币检查时间间隔'), 6, 0)
        grid.addWidget(self.lineBtcCheckInterval, 6, 1)
        #grid.addWidget(Label(u'重新报价时间间隔范围'), 7, 0)
        #grid.addWidget(self.linePlaceOrderInterval, 7, 1)
        grid.addWidget(Label(u'每次刷单数量'), 8, 0)
        grid.addWidget(self.lineSelfTradeVolume, 8, 1)

        self.getsettingForVTSymbol()  # 根据vtsymbol读取配置

        # 关联更新
        self.comboVtSymbol.currentIndexChanged.connect(self.getsettingForVTSymbol)
        self.buttonSaveSetting.clicked.connect(self.saveSettingForVTSymbol)
        self.buttonSwitchEngineStatus.clicked.connect(self.switchEngineStatus)

        hbox = QtWidgets.QHBoxLayout()
        #hbox.addWidget(self.buttonClearOrderFlowCount)
        #hbox.addWidget(self.buttonClearTradeCount)
        hbox.addStretch()
        hbox.addWidget(self.buttonSaveSetting)  # 不能用self
        #hbox.addWidget(buttonActivate)
        hbox.addWidget(self.buttonSwitchEngineStatus)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(grid)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

    def getsettingForVTSymbol(self):
        """根据交易对读取配置信息"""
        self.vtSymbol = str(self.comboVtSymbol.currentText())
        if self.vtSymbol:
            setting = self.followBtcEngine.settingsDict[self.vtSymbol]
        else:
            return

        self.lineSymbolBasicPrice.setText(str(setting['symbolBasicPrice']))
        self.lineBtcBasicPrice.setText(str(setting['btcBasicPrice']))
        self.lineOrderLevel.setText(str(setting['orderLevel']))
        self.lineOrderPriceGap.setText(str(setting['orderPriceGap']))
        self.lineOrderVolume.setText(str(setting['orderVolume']))
        self.lineBtcCheckInterval.setText(str(setting['btcCheckInterval']))
        #self.linePlaceOrderInterval.setText(str(setting['placeOrderInterval']))
        self.lineSelfTradeVolume.setText(str(setting['selfTradeVolume']))

    def getSettingFromMenu(self):
        # 写入配置到settingsDict
        try:
            setting = self.followBtcEngine.settingsDict[self.vtSymbol]

            setting['symbolBasicPrice'] = float(self.lineSymbolBasicPrice.text())
            setting['btcBasicPrice'] = float(self.lineBtcBasicPrice.text())
            setting['orderLevel'] = int(self.lineOrderLevel.text())
            setting['orderPriceGap'] = float(self.lineOrderPriceGap.text())
            setting['orderVolume'] = float(self.lineOrderVolume.text())
            setting['btcCheckInterval'] = float(self.lineBtcCheckInterval.text())
            #self.followBtcEngine.settingsDict[self.vtSymbol]['placeOrderInterval'] = float(self.linePlaceOrderInterval.text())
            setting['selfTradeVolume'] = float(self.lineSelfTradeVolume.text())
        except Exception as e:
            print(e)

    def saveSettingForVTSymbol(self):
        self.getSettingFromMenu()
        self.followBtcEngine.saveSetting()

    def switchEngineStatus(self):
        self.updateEngineStatus()
        self.followBtcEngine.switchEngineStatus()

    def updateEngineStatus(self):
        """更新引擎状态"""
        if self.followBtcEngine.active:
            self.buttonSwitchEngineStatus.setText(u'BTC跟随报价刷单引擎运行中')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: green")
        else:
            self.buttonSwitchEngineStatus.setText(u'BTC跟随报价刷单引擎已停止')
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: gray")
