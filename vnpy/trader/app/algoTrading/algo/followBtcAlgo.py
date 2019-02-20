# encoding: UTF-8

from __future__ import division
import json
from collections import OrderedDict

from vnpy.trader.vtConstant import (DIRECTION_LONG, DIRECTION_SHORT,
                                    OFFSET_OPEN, OFFSET_CLOSE)
from vnpy.trader.uiQt import QtWidgets
from vnpy.trader.app.algoTrading.algoTemplate import AlgoTemplate
from vnpy.trader.app.algoTrading.uiAlgoWidget import AlgoWidget, QtWidgets
from vnpy.trader.vtFunction import getJsonPath
from vnpy.trader.vtObject import VtLogData

########################################################################
class followBtcAlgo(AlgoTemplate):
    #跟随比特币价格，产生买卖报价
    
    templateName = u'followBtc 跟随比特币报单'

    #----------------------------------------------------------------------
    def __init__(self, engine, setting, algoName):
        """Constructor"""
        super().__init__(engine, setting, algoName)

        # 参数，强制类型转换，保证从CSV加载的配置正确
        self.gateway = str(setting['gateway'])            # gateway代码
        self.vtSymbol = str(setting['vtSymbol'])            # 交易对代码
        self.orderVolume = float(setting['orderVolume'])    # 委托数量
        self.interval = int(setting['interval'])            # 运行间隔
        self.minTickSpread = int(setting['minTickSpread'])  # 最小价差
        
        self.count = 0              # 定时计数
        self.tradedVolume = 0       # 总成交数量
        
        self.subscribe(self.vtSymbol)
        self.paramEvent()
        self.varEvent()
    
    #----------------------------------------------------------------------
    def onTick(self, tick):
        """"""
        pass   
        
    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """"""
        self.tradedVolume += trade.volume
        self.varEvent()
    
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """"""
        pass
    
    #----------------------------------------------------------------------
    def onTimer(self):
        """"""
        self.count += 1
        if self.count == self.interval:
            self.count = 0
            
            # 全撤委托
            self.cancelAll()
            
            # 获取行情
            tick = self.getTick(self.vtSymbol)
            if not tick:
                return
            
            contract = self.getContract(self.vtSymbol)
            if not contract:
                return
            
            tickSpread = (tick.askPrice1 - tick.bidPrice1) / contract.priceTick
            if tickSpread < self.minTickSpread:
                self.writeLog(u'当前价差为%s个Tick，小于算法设置%s，不执行刷单' %(tickSpread, self.minTickSpread))
                return
            
            midPrice = tick.bidPrice1 + contract.priceTick * int(tickSpread/2)
            
            self.buy(self.vtSymbol, midPrice, self.orderVolume)
            self.sell(self.vtSymbol, midPrice, self.orderVolume)
            
            self.writeLog(u'发出刷单买卖委托，价格：%s，数量：%s' %(midPrice, self.orderVolume))
        
        self.varEvent()
        
    #----------------------------------------------------------------------
    def onStop(self):
        """"""
        self.writeLog(u'停止算法')
        self.varEvent()
        
    #----------------------------------------------------------------------
    def varEvent(self):
        """更新变量"""
        d = OrderedDict()
        d[u'算法状态'] = self.active
        d[u'成交数量'] = self.tradedVolume
        d[u'定时计数'] = self.count
        d['active'] = self.active
        self.putVarEvent(d)
    
    #----------------------------------------------------------------------
    def paramEvent(self):
        """更新参数"""
        d = OrderedDict()
        d[u'代码'] = self.vtSymbol
        d[u'单次委托数量'] = self.orderVolume
        d[u'执行间隔'] = self.interval
        d[u'最小价差Tick'] = self.minTickSpread    
        self.putParamEvent(d)


########################################################################
class followBtcWidget(AlgoWidget):
    """"""
    
    #----------------------------------------------------------------------
    def __init__(self, algoEngine, parent=None):
        """Constructor"""
        super().__init__(algoEngine, parent)
        # 先调用initAlgoLayout

        self.templateName = followBtcAlgo.templateName
        return

        self.gateway = str(setting['gateway'])  # gateway代码
        self.symbol = str(setting['symbol'])  # 交易对代码
        self.vtSymbol = '.'.join([self.symbol, self.exchange])  # gateway.交易对代码
        self.symbolBasicPrice = setting['symbolBasicPrice']  # 代币交易对基准价
        self.btcBasicPrice = setting['btcBasicPrice']  # 比特币基准价 美元计价
        self.orderLevel = setting['orderLevel']  # 买卖档数 5-20
        self.orderPriceGap = setting['orderPriceGap']  # 档间价差
        self.orderVolume = setting['orderVolume']  # 每档挂单数量
        self.btcCheckInterval = setting['btcCheckInterval']  # 比特币检查时间间隔
        self.placeOrderInterval = setting['placeOrderInterval']  # 重新报价时间间隔

    #----------------------------------------------------------------------
    def initAlgoLayout(self):
        """"""
        self.fileName = 'AlgoConfig/' + 'followBtc.json'
        self.filePath = getJsonPath(self.fileName, __file__)
        try:
            f = open(self.filePath)
        except IOError:
            log = VtLogData()
            log.logContent = u'读取连接配置出错，请检查'+self.fileName
            self.writeLog(log)
            return

        # 解析json文件
        settings = json.load(f)
        f.close()
        self.configDict = {}

        self.vtSymbolList=settings.keys()
        try:
            for key in settings.keys():
                data = settings[key]
                print(data)
                vtsymbol = '.'.join([data['gateway'], data['symbol']])
                self.configDict[vtsymbol] = data
        except Exception as e:
            print(e)

        self.comboVtSymbol = QtWidgets.QComboBox()
        self.comboVtSymbol.addItems(self.configDict.keys())

        self.lineSymbol = QtWidgets.QLineEdit()
        self.lineSymbolBasicPrice = QtWidgets.QLineEdit()
        self.lineBtcBasicPrice = QtWidgets.QLineEdit()
        self.lineOrderLevel = QtWidgets.QLineEdit()
        self.lineOrderPriceGap = QtWidgets.QLineEdit()
        self.lineOrderVolume = QtWidgets.QLineEdit()
        self.lineBtcCheckInterval = QtWidgets.QLineEdit()
        self.linePlaceOrderInterval = QtWidgets.QLineEdit()


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
        grid.addWidget(Label(u'重新报价时间间隔范围'), 7, 0)
        grid.addWidget(self.linePlaceOrderInterval, 7, 1)

        self.getConfigForVTSymbol()  # 根据vtsymbol读取配置

        # 关联更新
        self.comboVtSymbol.currentIndexChanged.connect(self.getConfigForVTSymbol)
        return grid

    def getConfigForVTSymbol(self):
        """根据交易对读取配置信息"""
        self.vtSymbol = str(self.comboVtSymbol.currentText())
        if self.vtSymbol:
            config = self.configDict[self.vtSymbol]
        else:
            return

        self.lineSymbolBasicPrice.setText(str(config['symbolBasicPrice']))
        self.lineBtcBasicPrice.setText(str(config['btcBasicPrice']))
        self.lineOrderLevel.setText(str(config['orderLevel']))
        self.lineOrderPriceGap.setText(str(config['orderPriceGap']))
        self.lineOrderVolume.setText(str(config['orderVolume']))
        self.lineBtcCheckInterval.setText(str(config['btcCheckInterval']))
        self.linePlaceOrderInterval.setText(str(config['placeOrderInterval']))

    def getAlgoSetting(self):
        """"""
        setting = OrderedDict()
        setting['templateName'] = followBtcAlgo.templateName
        setting['vtSymbol'] = str(self.lineSymbol.text())
        setting['orderVolume'] = float(self.spinVolume.value())
        setting['interval'] = int(self.spinInterval.value())
        setting['minTickSpread'] = int(self.spinMinTickSpread.value())
        
        return setting

    def save(self):
        with open(self.filePath, "w") as f:
            json.dump(self.configDict, f)
