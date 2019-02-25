# encoding: UTF-8

'''
本文件中实现了跟随BTC行情报价与刷单引擎
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
from vnpy.trader.app.alGo.followBtcSelfTrade.coinbaseBtcTrade import CoinbaseWatch

########################################################################
class FollowBtcEngine(object):
    """跟随BTC刷单引擎"""
    settingFileName = 'followBtc_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    name = u'跟随BTC刷单模块'

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
        self.registerEvent()
        self.gatewayName = 'IDCM'
        self.curGateway = self.mainEngine.getGateway(self.gatewayName)

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
        #self.eventEngine.register(EVENT_TRADE, self.updateTrade)
        #self.eventEngine.register(EVENT_TIMER, self.updateTimer)
        #self.eventEngine.register(EVENT_ORDER, self.updateOrder)
        #self.eventEngine.register(EVENT_ACCOUNT, self.updateAccount)
        
    def startTrade(self):
        print('call starttrade')
        # 启动BTC跟随算法
        self.btcGateway = CoinbaseWatch()
        self.btcGateway.connect()
        time.sleep(3)
        try:
            for key in self.settingsDict:
                if self.settingsDict[key]['active']==True:
                    self.loopPlaceOrder(self.settingsDict[key])
        except Exception as e:
            print(e)

    # 循环产生订单
    def loopPlaceOrder(self, setting):
        while self.active:
            time.sleep(setting['btcCheckInterval'])  # 定期轮询

            self.cancelAll()  # 先全部撤单

            curBtcPrice = float(self.btcGateway.getLatestPrice())  # 需要加入取回价格错误的处理，设定3000-5000为有效价格
            if curBtcPrice < 0:
                time.sleep(5)
                curBtcPrice = self.btcGateway.getLatestPrice()
            if curBtcPrice == 0:
                self.writeLog("无法获取BTC基准价格")
                return
            if curBtcPrice <= 3000:
                self.writeLog("BTC基准价格%s异常" %(curBtcPrice))
                return
            orderBasicPrice = float(curBtcPrice) / float(setting['btcBasicPrice']) * float(setting['symbolBasicPrice'])  # 当前基准价

            for orderLevel in range(int(setting['orderLevel'])):
                self.sendOrder(orderBasicPrice, direction=0, orderLevel=orderLevel, setting=setting)
                self.sendOrder(orderBasicPrice, direction=1, orderLevel=orderLevel, setting=setting)

    # 停止BTC跟随交易
    def stopTrade(self):
        self.cancelAll()
        self.btcGateway.stop()

    def sendOrder(self, orderBasicPrice, direction, orderLevel, setting):
        # 发单

        # 计算价格 0 买入 1 卖出
        if direction == 0:
            price = orderBasicPrice * (1 - random.uniform(orderLevel, orderLevel+1)/100)
        else:
            price = orderBasicPrice * (1 + random.uniform(orderLevel, orderLevel+1)/100)

        # 计算数量
        #volume = setting['orderVolume']*random.random()
        volume = 10 + random.randint(1, setting['orderVolume'])  # 10为最小数量

        # 委托
        req = VtOrderReq()
        req.symbol = setting['symbol']
        req.vtSymbol = setting['gateway'] + '.' + setting['symbol']
        req.price = round(price, 4)  # 4位小数
        req.volume = volume
        if direction == 0:
            req.direction = '买入'  # 0 买入 1 卖出
        else:
            req.direction = '卖出'
        req.orderType = '限价'  # 限价

        try:
            self.mainEngine.sendOrder(req, self.gatewayName)
        except Exception as e:
            print("sendOrder")
            print(e)

    def cancelAll(self):
        """撤销所有委托"""
        if hasattr(self.curGateway, 'cancelAllOrders'):
            self.curGateway.cancelAllOrders()
            return

        l = self.mainEngine.getAllWorkingOrders()
        for order in l:
            self.mainEngine.cancelOrder(order, order.gatewayName)

    #----------------------------------------------------------------------
    def updateOrder(self, event):
        #更新成交数据
        # 只需要需要撤单委托
        order = event.dict_['data']
        if order.status != STATUS_CANCELLED:
            return
        
        if order.symbol not in self.orderCancelDict:
            self.orderCancelDict[order.symbol] = 1
        else:
            self.orderCancelDict[order.symbol] += 1

    #----------------------------------------------------------------------
    def updateTrade(self, event):
        """更新成交数据"""
        trade = event.dict_['data']
        self.tradeCount += trade.volume

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
            self.writeLog(u'BTC跟随报价刷单功能启动')
            self.reqThread = Thread(target=self.startTrade)
            self.reqThread.start()
            #self.startTrade()
        else:
            self.writeLog(u'BTC跟随报价刷单功能停止')

            self.stopTrade()
            
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        self.saveSetting()
        
