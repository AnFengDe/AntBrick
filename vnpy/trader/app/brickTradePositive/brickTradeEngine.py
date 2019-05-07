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

    name = u'主动搬砖模块'

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
        self.onOrderFallback = None
        self.onOrderFilled = None
        self.onOrderCancelled = None
        self.brickMap = {}

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
            "bid":float(tick.bidPrice1),
            "bidVolume":float(tick.bidVolume1),
            "ask":float(tick.askPrice1),
            "askVolume": float(tick.askVolume1),
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
                if self.stage == 0 and self.jccGateway.accountDict["JMOAC"].available >= self.settingsDict["amount"] and \
                        self.coinBeneGateway.accountDict["USDT"].available > usdt_amount:
                    self.stage = 1
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["bid"]
                    orderReq.currencyGet = "CNY"
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.currencyPay = "JMOAC"
                    orderReq.direction = DIRECTION_SELL
                    orderReq.symbol = "JMOAC-CNY"
                    orderReq.volume = self.settingsDict["amount"]
                    orderReq.price = self.marketInfo["JCC.JMOAC-CNY"]["bid"]
                    self.writeLog(u'主动搬砖挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["JCC.JMOAC-CNY"]["bid"]))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        if self.brickMap[order.vtOrderID]['status'] == 'ordered':
                            self.brickMap[order.vtOrderID]['status'] = 'filled'
                            orderReq = VtOrderReq()
                            orderReq.price = self.marketInfo["COINBENE.MOACUSDT"]["ask"]
                            orderReq.volume = self.settingsDict["amount"]  # 交易数量
                            orderReq.symbol = "MOACUSDT"  # 交易对
                            orderReq.direction = DIRECTION_BUY  # 限价买入
                            self.writeLog(
                                u'对冲挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["COINBENE.MOACUSDT"]["ask"]))

                            def on_order_fallback2():
                                self.coinBeneGateway.sendOrder(orderReq)
                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order):
                                self.stage = 0
                            self.onOrderFilled = on_order_filled2
                            self.coinBeneGateway.sendOrder(orderReq)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
            gap = self.marketInfo["COINBENE.MOACUSDT"]["bid"] / (
                    self.marketInfo["JCC.JMOAC-CNY"]["ask"] * self.settingsDict["exchangeRate"]["CNY_USD"]) - 1
            if gap > self.settingsDict["gapLimit"]:
                print("MOAC: COINBENE BID:%f\tJCC ASK:%f\t Gap: %f" % (self.marketInfo["COINBENE.MOACUSDT"]["bid"], self.marketInfo["JCC.JMOAC-CNY"]["ask"], gap))
                cny_amount = self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"]
                if self.stage == 0 and self.jccGateway.accountDict["CNY"].available >= cny_amount and \
                        self.coinBeneGateway.accountDict["MOAC"].available > self.settingsDict["amount"]:
                    self.stage = 2
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"]
                    orderReq.currencyGet = "JMOAC"
                    orderReq.valuePay = round(self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"], 6)
                    orderReq.currencyPay = "CNY"
                    orderReq.direction = DIRECTION_BUY
                    orderReq.symbol = "JMOAC-CNY"
                    orderReq.volume = self.settingsDict["amount"]
                    orderReq.price = self.marketInfo["JCC.JMOAC-CNY"]["ask"]
                    self.writeLog(u'主动搬砖挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["JCC.JMOAC-CNY"]["ask"]))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        if self.brickMap[order.vtOrderID]['status'] == 'ordered':
                            self.brickMap[order.vtOrderID]['status'] = 'filled'
                            orderReq = VtOrderReq()
                            orderReq.price = self.marketInfo["COINBENE.MOACUSDT"]["bid"]
                            orderReq.volume = self.settingsDict["amount"]  # 交易数量
                            orderReq.symbol = "MOACUSDT"  # 交易对
                            orderReq.direction = DIRECTION_SELL  # 限价卖出
                            self.writeLog(u'对冲挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["COINBENE.MOACUSDT"]["bid"]))

                            def on_order_fallback2():
                                self.coinBeneGateway.sendOrder(orderReq)
                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order):
                                self.stage = 0
                            self.onOrderFilled = on_order_filled2
                            self.coinBeneGateway.sendOrder(orderReq)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
            if self.stage == 0:
                price_with_gap = (1 - self.settingsDict["gapLimit"]) * (self.marketInfo["JCC.JMOAC-CNY"]["bid"]) * \
                                 self.settingsDict["exchangeRate"]["CNY_USD"]
                if price_with_gap > self.marketInfo["COINBENE.MOACUSDT"]["bid"] + self.settingsDict['step'] and self.jccGateway.accountDict["JMOAC"].available >= self.settingsDict["amount"] and \
                        self.coinBeneGateway.accountDict["USDT"].available >= self.settingsDict["amount"] * self.marketInfo["COINBENE.MOACUSDT"]["bid"]:
                    gap = (self.marketInfo["JCC.JMOAC-CNY"]["bid"] * self.settingsDict["exchangeRate"]["CNY_USD"]) / \
                          self.marketInfo["COINBENE.MOACUSDT"]["bid"] - 1
                    price = self.marketInfo["COINBENE.MOACUSDT"]["bid"] + self.settingsDict['step']
                    if price > self.marketInfo["COINBENE.MOACUSDT"]["ask"]:
                        price = self.marketInfo["COINBENE.MOACUSDT"]["ask"]
                    print("MOAC: JCC BID:%f\tCOINBENE BID:%f\t Gap: %f" % (
                    self.marketInfo["JCC.JMOAC-CNY"]["bid"], price_with_gap, gap))
                    self.stage = 3
                    orderReq = VtOrderReq()
                    orderReq.price = price
                    orderReq.volume = self.settingsDict["amount"]  # 交易数量
                    orderReq.symbol = "MOACUSDT"  # 交易对
                    orderReq.direction = DIRECTION_BUY  # 限价买入
                    self.writeLog(u'主动搬砖买一盘口挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["COINBENE.MOACUSDT"]["bid"] + self.settingsDict['step']))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        def trade_logic(order):
                            orderReq = VtOrderReq()
                            orderReq.valueGet = round(order.tradedVolume * self.marketInfo["JCC.JMOAC-CNY"]["bid"], 6)
                            orderReq.currencyGet = "CNY"
                            orderReq.valuePay = order.tradedVolume
                            orderReq.currencyPay = "JMOAC"
                            orderReq.direction = DIRECTION_SELL
                            orderReq.symbol = "JMOAC-CNY"
                            orderReq.volume = order.tradedVolume
                            orderReq.price = self.marketInfo["JCC.JMOAC-CNY"]["bid"]
                            self.writeLog(
                                u'主动搬砖对冲挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["JCC.JMOAC-CNY"]["bid"]))
                            self.stage = 4

                            def on_order_fallback2():
                                self.jccGateway.sendOrder(orderReq)

                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order):
                                self.stage = 0

                            self.onOrderFilled = on_order_filled2
                            self.jccGateway.sendOrder(orderReq)

                        if order.status == STATUS_PARTTRADED:

                            def trade_order_cancelled(order2):
                                if order2.orderID == order.orderID:
                                    self.brickMap[order.vtOrderID]['watchStatus'] = False
                                    trade_logic(self.brickMap[order.vtOrderID]['order'])
                            self.onOrderCancelled = trade_order_cancelled
                            self.coinBeneGateway.cancelOrder(order)
                        else:
                            trade_logic(self.brickMap[order.vtOrderID]['order'])
                    self.onOrderFilled = on_order_filled
                    self.coinBeneGateway.sendOrder(orderReq)
                price_with_gap = (1 + self.settingsDict["gapLimit"]) * (self.marketInfo["JCC.JMOAC-CNY"]["ask"]) * \
                                 self.settingsDict["exchangeRate"]["CNY_USD"]
                cny_amount = self.settingsDict["amount"] * (self.marketInfo["COINBENE.MOACUSDT"]["ask"] - self.settingsDict['step']) / self.settingsDict["exchangeRate"]["CNY_USD"]
                if price_with_gap < self.marketInfo["COINBENE.MOACUSDT"]["ask"] - self.settingsDict['step'] and self.jccGateway.accountDict["CNY"].available >= cny_amount and \
                        self.coinBeneGateway.accountDict["MOAC"].available >= self.settingsDict["amount"]:
                    price = self.marketInfo["COINBENE.MOACUSDT"]["ask"] - self.settingsDict['step']
                    if price < self.marketInfo["COINBENE.MOACUSDT"]["bid"]:
                        price = self.marketInfo["COINBENE.MOACUSDT"]["bid"]
                    gap = self.marketInfo["COINBENE.MOACUSDT"]["ask"] / (
                                self.marketInfo["JCC.JMOAC-CNY"]["ask"] * self.settingsDict["exchangeRate"]["CNY_USD"]) - 1
                    print("MOAC: JCC ASK:%f\tCOINBENE ASK:%f\t Gap: %f" % (
                    self.marketInfo["JCC.JMOAC-CNY"]["ask"], price_with_gap, gap))
                    self.stage = 5
                    orderReq = VtOrderReq()
                    orderReq.price = price
                    orderReq.volume = self.settingsDict["amount"]  # 交易数量
                    orderReq.symbol = "MOACUSDT"  # 交易对
                    orderReq.direction = DIRECTION_SELL  # 限价卖出
                    self.writeLog(u'主动搬砖买一盘口挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["COINBENE.MOACUSDT"]["ask"] - self.settingsDict['step']))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        def trade_logic(order):
                            orderReq = VtOrderReq()
                            orderReq.valueGet = self.settingsDict["amount"]
                            orderReq.currencyGet = "JMOAC"
                            orderReq.valuePay = round(self.settingsDict["amount"] * self.marketInfo["JCC.JMOAC-CNY"]["ask"], 6)
                            orderReq.currencyPay = "CNY"
                            orderReq.direction = DIRECTION_BUY
                            orderReq.symbol = "JMOAC-CNY"
                            orderReq.volume = order.tradedVolume
                            orderReq.price = self.marketInfo["JCC.JMOAC-CNY"]["ask"]
                            self.writeLog(u'主动搬砖对冲挂单：%s, 单价：%.4f' % (orderReq.symbol, self.marketInfo["JCC.JMOAC-CNY"]["ask"]))
                            self.stage = 6

                            def on_order_fallback2():
                                self.jccGateway.sendOrder(orderReq)
                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order):
                                self.stage = 0
                            self.onOrderFilled = on_order_filled2
                            self.jccGateway.sendOrder(orderReq)

                        if order.status == STATUS_PARTTRADED:

                            def trade_order_cancelled(order2):
                                if order2.orderID == order.orderID:
                                    trade_logic(self.brickMap[order.vtOrderID]['order'])

                            self.onOrderCancelled = trade_order_cancelled
                            self.coinBeneGateway.cancelOrder(order)
                        else:
                            trade_logic(self.brickMap[order.vtOrderID]['order'])
                    self.onOrderFilled = on_order_filled
                    self.coinBeneGateway.sendOrder(orderReq)
            if self.stage == 3:
                price_with_gap = (1 - self.settingsDict["gapLimit"]) * (self.marketInfo["JCC.JMOAC-CNY"]["bid"]) * self.settingsDict["exchangeRate"]["CNY_USD"]
                for vtOrderId in self.brickMap:
                    if vtOrderId.startswith("COINBENE.") and self.brickMap[vtOrderId]['status'] == 'ordered':
                        price = self.brickMap[vtOrderId]['order'].price
                        if price_with_gap < price:
                            self.brickMap[vtOrderId]['status'] = 'canceled'
                            self.writeLog(u'主动搬砖盘口撤单：%s, 单价：%.4f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled =  order_cancelled
                            self.coinBeneGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        if price < round(self.marketInfo["COINBENE.MOACUSDT"]["bid"], 3) and price_with_gap > round(price + self.settingsDict['step']):
                            self.brickMap[vtOrderId]['status'] = 'canceled'
                            self.writeLog(u'主动搬砖盘口撤单：%s, 单价：%.4f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled =  order_cancelled
                            self.coinBeneGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
            if self.stage == 5:
                price_with_gap = (1 + self.settingsDict["gapLimit"]) * (self.marketInfo["JCC.JMOAC-CNY"]["ask"]) * self.settingsDict["exchangeRate"]["CNY_USD"]
                for vtOrderId in self.brickMap:
                    if vtOrderId.startswith("COINBENE.") and self.brickMap[vtOrderId]['status'] == 'ordered':
                        price = self.brickMap[vtOrderId]['order'].price
                        if price_with_gap > price:
                            self.brickMap[vtOrderId]['status'] = 'canceled'
                            self.writeLog(u'主动搬砖盘口撤单：%s, 单价：%.4f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.coinBeneGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        if price > round(self.marketInfo["COINBENE.MOACUSDT"]["ask"], 3) and price_with_gap > round(price - self.settingsDict['step']):
                            self.brickMap[vtOrderId]['status'] = 'canceled'
                            self.writeLog(u'主动搬砖盘口撤单：%s, 单价：%.4f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.coinBeneGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
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

    #----------------------------------------------------------------------
    def updateOrder(self, event):
        #更新下单数据
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return
        order = event.dict_['data']
        if order.status == STATUS_CANCELLED:
            if self.onOrderCancelled is not None:
                self.onOrderCancelled(order)
        if order.status == STATUS_ORDERED:
            self.onOrderFallback = None
            if order.vtSymbol == "COINBENE.MOACUSDT":
                watchThread = Thread(target=self.watchCoinBeneOrder, args=(order.orderID, order.vtOrderID))
                self.brickMap[order.vtOrderID] = {
                    'order': order,
                    'status': 'ordered',
                    'watchThread': watchThread,
                    'watchStatus': True
                }
                watchThread.start()
                # self.stage = 0
            elif order.vtSymbol == "JCC.JMOAC-CNY":
                self.brickMap[order.vtOrderID] = {
                    'order': order,
                    'status': 'ordered',
                }
                pass
        elif order.status == STATUS_ALLTRADED:
            if order.vtSymbol == "COINBENE.MOACUSDT":
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                    self.brickMap[order.vtOrderID]['watchStatus'] = False
                    self.brickMap[order.vtOrderID]['order'] = order
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
            else:
                self.onOrderFilled(order)
        elif order.status == STATUS_PARTTRADED:
            if order.vtSymbol == "COINBENE.MOACUSDT":
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                    self.brickMap[order.vtOrderID]['order'] = order
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
        elif order.status == STATUS_REJECTED:
            if self.onOrderFallback is not None:
                self.onOrderFallback()


    def watchCoinBeneOrder(self, order_id, vt_order_id):
        while self.brickMap[vt_order_id]['watchStatus'] and self.active:
            self.coinBeneGateway.queryOrder(order_id)
            time.sleep(1)

    #----------------------------------------------------------------------
    def updateTrade(self, event):
        """更新成交数据"""
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return


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

