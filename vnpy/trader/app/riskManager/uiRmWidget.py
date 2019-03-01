# encoding: UTF-8

'''
风控模块相关的GUI控制组件
'''


from vnpy.event import Event

from vnpy.trader.uiBasicWidget import QtGui, QtWidgets, QtCore
from vnpy.trader.app.riskManager.language import text


########################################################################
class RmSpinBox(QtWidgets.QSpinBox):
    """调整参数用的数值框"""

    #----------------------------------------------------------------------
    def __init__(self, value):
        """Constructor"""
        super(RmSpinBox, self).__init__()

        self.setMinimum(0)
        self.setMaximum(1000000)
        
        self.setValue(value)
    

########################################################################
class HorizonSplitLine(QtWidgets.QFrame):
    # 水平分割线
    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        super().__init__()
        self.setFrameShape(self.HLine)
        self.setFrameShadow(self.Sunken)


class SplitGrid(QtWidgets.QFormLayout):
    # 水平分割线
    def __init__(self):
        """Constructor"""
        super().__init__()
        lineSplit = HorizonSplitLine()
        self.addWidget(lineSplit)

########################################################################
class RmEngineManager(QtWidgets.QWidget):
    """风控引擎的管理组件"""

    #----------------------------------------------------------------------
    def __init__(self, rmEngine, eventEngine, parent=None):
        """Constructor"""
        super().__init__(parent)
        
        self.rmEngine = rmEngine
        self.eventEngine = eventEngine
        try:
            self.initUi()
        except Exception as e:
            print(e)
        self.updateEngineStatus()

    #----------------------------------------------------------------------
    def initUi(self):
        """初始化界面"""
        self.setWindowTitle(text.RISK_MANAGER)
        
        # 设置界面
        self.buttonSwitchEngineStatus = QtWidgets.QPushButton(text.RISK_MANAGER_STOP)
        self.comboVtSymbol = QtWidgets.QComboBox()
        for key in self.rmEngine.settingsDict.keys():
            if '.' in key:
                self.comboVtSymbol.addItem(key)

        self.lineAccWarnLimit = QtWidgets.QLineEdit()
        self.lineAccMinLimit = QtWidgets.QLineEdit()

        #self.lineSplit = RmLine()
        #self.lineSplit1 = RmLine()
        self.lineBar = QtWidgets.QToolBar()
        """
        self.spinOrderFlowLimit = RmSpinBox(self.rmEngine.orderFlowLimit)
        self.spinOrderFlowClear = RmSpinBox(self.rmEngine.orderFlowClear)
        self.spinOrderSizeLimit = RmSpinBox(self.rmEngine.orderSizeLimit)
        self.spinTradeLimit = RmSpinBox(self.rmEngine.tradeLimit)
        self.spinWorkingOrderLimit = RmSpinBox(self.rmEngine.workingOrderLimit)
        self.spinOrderCancelLimit = RmSpinBox(self.rmEngine.orderCancelLimit)
        
        self.spinMarginRatioLimit = RmSpinBox(self.rmEngine.marginRatioLimit * 100) # 百分比显示配置
        self.spinMarginRatioLimit.setMaximum(100)   
        self.spinMarginRatioLimit.setSuffix('%')
        
        """
        #buttonClearOrderFlowCount = QtWidgets.QPushButton(text.CLEAR_ORDER_FLOW_COUNT)
        #buttonClearTradeCount = QtWidgets.QPushButton(text.CLEAR_TOTAL_FILL_COUNT)
        self.buttonSaveSetting = QtWidgets.QPushButton(text.SAVE_SETTING)
        
        Label = QtWidgets.QLabel
        grid = QtWidgets.QGridLayout()
        grid.addWidget(Label(text.WORKING_STATUS), 0, 0)
        grid.addWidget(self.buttonSwitchEngineStatus, 0, 1)
        grid.addWidget(Label('代币代码'), 1, 0)
        grid.addWidget(self.comboVtSymbol, 1, 1)
        grid.addWidget(Label('账户余额预警值'), 2, 0)
        grid.addWidget(self.lineAccWarnLimit, 2, 1)
        grid.addWidget(Label('账户余额最低值'), 3, 0)
        grid.addWidget(self.lineAccMinLimit, 3, 1)
        #grid.addWidget(self.lineSplit, 4, 0)
        #grid.addWidget(self.lineSplit1, 4, 1)
        #grid.addWidget(self.lineBar, 5, 0)

        self.getSettingForVTSymbol()
        self.comboVtSymbol.currentIndexChanged.connect(self.getSettingForVTSymbol)

        hbox = QtWidgets.QHBoxLayout()
        #hbox.addWidget(buttonClearOrderFlowCount)
        #hbox.addWidget(buttonClearTradeCount)
        hbox.addStretch()
        hbox.addWidget(self.buttonSaveSetting)
        
        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(grid)

        #grid1 = SplitGrid()
        #vbox.addLayout(grid1)

        vbox.addLayout(hbox)
        self.setLayout(vbox)


        # 连接组件信号
        #buttonClearOrderFlowCount.clicked.connect(self.rmEngine.clearOrderFlowCount)
        #buttonClearTradeCount.clicked.connect(self.rmEngine.clearTradeCount)
        self.buttonSwitchEngineStatus.clicked.connect(self.switchEngineSatus)
        self.buttonSaveSetting.clicked.connect(self.saveSettingForVTSymbol)
        
        # 设为固定大小
        self.setFixedSize(self.sizeHint())

    def getSettingForVTSymbol(self):
        """根据交易对读取配置信息"""
        self.vtSymbol = str(self.comboVtSymbol.currentText())
        self.lineAccWarnLimit.setText(str(self.rmEngine.settingsDict[self.vtSymbol]['warnLimit']))
        self.lineAccMinLimit.setText(str(self.rmEngine.settingsDict[self.vtSymbol]['minLimit']))

    def saveSettingForVTSymbol(self):
        """写入配置信息"""
        self.rmEngine.settingsDict[self.vtSymbol]['warnLimit'] = float(self.lineAccWarnLimit.text())
        self.rmEngine.settingsDict[self.vtSymbol]['minLimit'] = float(self.lineAccMinLimit.text())

        self.rmEngine.saveSetting()

    #----------------------------------------------------------------------
    def switchEngineSatus(self):
        """控制风控引擎开关"""
        self.rmEngine.switchEngineStatus()
        self.updateEngineStatus()
        
    #----------------------------------------------------------------------
    def updateEngineStatus(self):
        """更新引擎状态"""
        if self.rmEngine.active:
            self.buttonSwitchEngineStatus.setText(text.RISK_MANAGER_RUNNING)
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: green")
        else:
            self.buttonSwitchEngineStatus.setText(text.RISK_MANAGER_STOP)
            self.buttonSwitchEngineStatus.setStyleSheet("background-color: gray")
