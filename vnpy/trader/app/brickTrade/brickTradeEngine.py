# encoding: UTF-8

'''
本文件中实现了搬砖引擎
'''

from __future__ import division

import json
import os
import platform
import time
import random
from threading import Thread

from vnpy.event import Event
from vnpy.trader.vtEvent import *
from vnpy.trader.vtConstant import *
from vnpy.trader.vtGateway import VtLogData
from vnpy.trader.vtFunction import getJsonPath
from vnpy.trader.vtObject import VtOrderReq

########################################################################
class BrickTradeEngine(object):
    """搬砖引擎"""
    settingFileName = 'brickTrade_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    name = u'搬砖模块'

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        # 是否启动引擎
        self.active = False

        self.orderFlowClear = EMPTY_INT  # 计数清空时间（秒）
        self.orderFlowTimer = EMPTY_INT     # 计数清空时间计时
        self.settingsDict = {}

        self.loadSetting()
        self.coinBeneGatewayName = 'COINBENE'
        self.coinBeneGateway = self.mainEngine.getGateway(self.coinBeneGatewayName)
        self.jccGatewayName = 'JCC'
        self.jccGateway = self.mainEngine.getGateway(self.jccGatewayName)
        self.marketInfo = {}
        self.stage = 0

    #----------------------------------------------------------------------
    def loadSetting(self):
        """读取配置"""
        with open(self.settingFilePath) as f:
            d = json.load(f)
            for key in d.keys():
                self.settingsDict[key] = d[key]

    #----------------------------------------------------------------------
    def saveSetting(self):
        """保存配置参数到文件"""
        with open(self.settingFilePath, 'w') as f:
            # 写入json
            jsonD = json.dumps(self.settingsDict, indent=4)
            #jsonD = json.dumps(d, indent=4)
            f.write(jsonD)

    #----------------------------------------------------------------------
    def registerEvent(self):
        """注册事件监听"""
        self.eventEngine.register(EVENT_TRADE, self.updateTrade)
        self.eventEngine.register(EVENT_TIMER, self.updateTimer)
        self.eventEngine.register(EVENT_ORDER, self.updateOrder)
        self.eventEngine.register(EVENT_TICK, self.updateTick)

    def unregisterEvent(self):
        """销毁事件监听"""
        self.eventEngine.unregister(EVENT_TRADE, self.updateTrade)
        self.eventEngine.unregister(EVENT_TIMER, self.updateTimer)
        self.eventEngine.unregister(EVENT_ORDER, self.updateOrder)
        self.eventEngine.unregister(EVENT_TICK, self.updateTick)

    def startTrade(self):
        print('call starttrade')
        self.marketInfo = {}
        self.stage = 0
        self.registerEvent()
        # 启动搬砖算法
        while self.active:
            self.jccGateway.exchangeApi.queryAccount()
            self.jccGateway.subscribe(None)
            self.jccGateway.exchangeApi.queryHistoryOrder()
            self.coinBeneGateway.restApi.queryAccount()
            self.coinBeneGateway.subscribe(None)
            time.sleep(1)

    def updateTick(self, event):
        """更新行情数据"""
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return
        self.marketInfo[tick.vtSymbol] = {
            "symbol":tick.vtSymbol,
            "time":tick.datetime,
            "last":float(tick.lastPrice),
            "bid":float(tick.bidPrice2),
            "bidVolume":float(tick.bidVolume2),
            "ask":float(tick.askPrice2),
            "askVolume": float(tick.askVolume2),
        }
        self.seekBrickGap()

    def seekBrickGap(self):
        if self.marketInfo.get("JCC.JMOAC-CNY") is not None and self.marketInfo.get("COINBENE.MOACUSDT") is not None:
            gap = (self.marketInfo["JCC.JMOAC-CNY"]["bid"] * self.settingsDict["exchangeRate"]["CNY_USD"]) / \
                  self.marketInfo["COINBENE.MOACUSDT"]["ask"] - 1
            if gap > self.settingsDict["gapLimit"]:
                print("MOAC: JCC BID:%f\tCOINBENE ASK:%f\t Gap: %f" % (self.marketInfo["JCC.JMOAC-CNY"]["bid"], self.marketInfo["COINBENE.MOACUSDT"]["ask"], gap))
                usdt_amount = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["bid"] * \
                              self.settingsDict["exchangeRate"]["CNY_USD"]
                if self.stage == 0 and self.jccGateway.accountDict["JMOAC"].balance >= self.settingsDict["amount"] and \
                        self.coinBeneGateway.accountDict["USDT"].balance > usdt_amount:
                    self.stage = 1
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["bid"]
                    orderReq.currencyGet = "CNY"
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.currencyPay = "JMOAC"
                    orderReq.direction = DIRECTION_SELL
                    orderReq.symbol = "JMOAC-CNY"
                    print(orderReq)
                    self.jccGateway.sendOrder(orderReq)
            elif self.stage == 0:
                price_with_gap = (self.settingsDict["gapLimit"] + 1) * self.marketInfo["COINBENE.MOACUSDT"]["ask"] / self.settingsDict["exchangeRate"]["CNY_USD"]
                print("MOAC: JCC BID:%f\tCOINBENE ASK:%f\t Gap: %f" % (price_with_gap, self.marketInfo["COINBENE.MOACUSDT"]["ask"], gap))
                usdt_amount = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"] * \
                              self.settingsDict["exchangeRate"]["CNY_USD"]
                if price_with_gap < self.marketInfo["JCC.JMOAC-CNY"]["ask"] - 0.02 and self.jccGateway.accountDict["JMOAC"].balance >= self.settingsDict["amount"] and \
                        self.coinBeneGateway.accountDict["USDT"].balance > usdt_amount:
                    self.stage = 1
                    orderReq = VtOrderReq()
                    orderReq.valueGet = round(self.settingsDict["amount"] * (self.marketInfo["JCC.JMOAC-CNY"]["ask"] - 0.02), 6)
                    orderReq.currencyGet = "CNY"
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.currencyPay = "JMOAC"
                    orderReq.direction = DIRECTION_SELL
                    orderReq.symbol = "JMOAC-CNY"
                    print(orderReq)
                    self.jccGateway.sendOrder(orderReq)
                    pass
            gap = self.marketInfo["COINBENE.MOACUSDT"]["bid"] / (
                    self.marketInfo["JCC.JMOAC-CNY"]["ask"] * self.settingsDict["exchangeRate"]["CNY_USD"]) - 1
            if gap > self.settingsDict["gapLimit"]:
                print("MOAC: COINBENE BID:%f\tJCC ASK:%f\t Gap: %f" % (self.marketInfo["COINBENE.MOACUSDT"]["bid"], self.marketInfo["JCC.JMOAC-CNY"]["ask"], gap))
                cny_amount = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"]
                if self.stage == 0 and self.jccGateway.accountDict["CNY"].balance >= cny_amount and \
                        self.coinBeneGateway.accountDict["MOAC"].balance > self.settingsDict["amount"]:
                    self.stage = 2
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"]
                    orderReq.currencyGet = "JMOAC"
                    orderReq.valuePay = round(self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"], 6)
                    orderReq.currencyPay = "CNY"
                    orderReq.direction = DIRECTION_BUY
                    orderReq.symbol = "JMOAC-CNY"
                    print(orderReq)
                    self.jccGateway.sendOrder(orderReq)
        pass

    # 停止搬砖交易
    def stopTrade(self):
        self.unregisterEvent()
        self.cancelAll()

    def cancelAll(self):
        """撤销所有委托"""
        if hasattr(self.jccGateway, 'cancelAllOrders'):
            self.jccGateway.cancelAllOrders()
            if hasattr(self.coinBeneGateway, 'cancelAllOrders'):
                self.coinBeneGateway.cancelAllOrders()
                return

        l = self.mainEngine.getAllWorkingOrders()
        for order in l:
            self.mainEngine.cancelOrder(order, order.gatewayName)

    #----------------------------------------------------------------------
    def updateOrder(self, event):
        #更新下单数据
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return
        order = event.dict_['data']
        if order.status == STATUS_ORDERED:
            if order.vtSymbol == "COINBENE.MOACUSDT" and self.stage == 1:
                # watchThread = Thread(target=self.watchCoinBeneOrder, args=(order.orderID, ))
                # watchThread.start()
                # self.stage = 0
                pass
            elif order.vtSymbol == "COINBENE.MOACUSDT" and self.stage == 2:
                # self.stage = 0
                pass
            elif order.vtSymbol == "JCC.JMOAC-CNY":
                pass

    def watchCoinBeneOrder(self, orderid):
        while True:
            self.coinBeneGateway.queryOrder(orderid)
            time.sleep(1)
            pass

    #----------------------------------------------------------------------
    def updateTrade(self, event):
        """更新成交数据"""
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return

        # 不处理撤单委托
        order = event.dict_['data']
        if order.status == STATUS_ALLTRADED:
            if order.vtSymbol == "JCC.JMOAC-CNY" and self.stage == 1:
                orderReq = VtOrderReq()
                orderReq.price = self.marketInfo["COINBENE.MOACUSDT"]["ask"]
                orderReq.volume = self.settingsDict["amount"]  # 交易数量
                orderReq.symbol = "MOACUSDT"  # 交易对
                orderReq.direction = DIRECTION_BUY  # 限价买入
                print(orderReq)
                self.coinBeneGateway.sendOrder(orderReq)
            elif order.vtSymbol == "JCC.JMOAC-CNY" and self.stage == 2:
                orderReq = VtOrderReq()
                orderReq.price = self.marketInfo["COINBENE.MOACUSDT"]["bid"]
                orderReq.volume = self.settingsDict["amount"]  # 交易数量
                orderReq.symbol = "MOACUSDT"  # 交易对
                orderReq.direction = DIRECTION_SELL  # 限价卖出
                print(orderReq)
                self.coinBeneGateway.sendOrder(orderReq)


    #----------------------------------------------------------------------
    def updateTimer(self, event):
        """更新定时器"""
        self.orderFlowTimer += 1

        # 如果计时超过了流控清空的时间间隔，则执行清空
        if self.orderFlowTimer >= self.orderFlowClear:
            self.orderFlowCount = 0
            self.orderFlowTimer = 0

    #----------------------------------------------------------------------
    def writeLog(self, content):
        """快速发出日志事件"""
        # 发出报警提示音

        if platform.uname() == 'Windows':
            import winsound
            winsound.PlaySound("SystemHand", winsound.SND_ASYNC)

        # 发出日志事件
        log = VtLogData()
        log.logContent = content
        log.gatewayName = self.name
        event = Event(type_=EVENT_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)

    #----------------------------------------------------------------------
    def clearOrderFlowCount(self):
        """清空流控计数"""
        self.orderFlowCount = 0
        self.writeLog(u'清空流控计数')

    #----------------------------------------------------------------------
    def clearTradeCount(self):
        """清空成交数量计数"""
        self.tradeCount = 0
        self.writeLog(u'清空总成交计数')

    #----------------------------------------------------------------------
    def setOrderFlowLimit(self, n):
        """设置流控限制"""
        self.orderFlowLimit = n

    #----------------------------------------------------------------------
    def setOrderFlowClear(self, n):
        """设置流控清空时间"""
        self.orderFlowClear = n

    #----------------------------------------------------------------------
    def setOrderSizeLimit(self, n):
        """设置委托最大限制"""
        self.orderSizeLimit = n

    #----------------------------------------------------------------------
    def setTradeLimit(self, n):
        """设置成交限制"""
        self.tradeLimit = n

    #----------------------------------------------------------------------
    def setWorkingOrderLimit(self, n):
        """设置活动合约限制"""
        self.workingOrderLimit = n

    #----------------------------------------------------------------------
    def setOrderCancelLimit(self, n):
        """设置单合约撤单次数上限"""
        self.orderCancelLimit = n

    #----------------------------------------------------------------------
    def setMarginRatioLimit(self, n):
        """设置保证金比例限制"""
        self.marginRatioLimit = n/100   # n为百分数，需要除以100

    #----------------------------------------------------------------------
    def switchEngineStatus(self):
        """开关引擎"""
        self.active = not self.active

        if self.active:
            self.writeLog(u'搬砖功能启动')
            self.reqThread = Thread(target=self.startTrade)
            self.reqThread.start()
            #self.startTrade()
        else:
            self.writeLog(u'搬砖功能停止')

            self.stopTrade()
            
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        self.saveSetting()

