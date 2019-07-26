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
    settingFileName = 'brickTradePassive_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    name = u'被动搬砖模块'

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
        self.coinwGatewayName = 'Coinw'
        self.coinwGateway = self.mainEngine.getGateway(self.coinwGatewayName)
        self.jccGatewayName = 'JCC'
        self.jccGateway = self.mainEngine.getGateway(self.jccGatewayName)
        self.marketInfo = {}
        self.stage = 0
        self.onOrderFallback = None
        self.onOrderFilled = None
        self.onOrderCancelled = None

        self.fromGatewayName = self.settingsDict["gatewaySettings"]["fromGatewayName"]
        self.initGatewaySettings()
        self.VT_SYMBOL_A = self.settingsDict["gatewaySettings"][self.fromGatewayName]["VT_SYMBOL"]
        self.SYMBOL_A = self.settingsDict["gatewaySettings"][self.fromGatewayName]["SYMBOL"]
        self.CURRENCY_SYMBOLS_A = self.settingsDict["gatewaySettings"][self.fromGatewayName]["CURRENCY_SYMBOLS"]
        self.VT_SYMBOL_B = self.settingsDict["gatewaySettings"]["JCC"]["VT_SYMBOL"]
        self.SYMBOL_B = self.settingsDict["gatewaySettings"]["JCC"]["SYMBOL"]
        self.CURRENCY_SYMBOLS_B = self.settingsDict["gatewaySettings"]["JCC"]["CURRENCY_SYMBOLS"]
        self.brickMap = {}
        self.accountInfo = {}
        self.ticked_a = False
        self.ticked_b = False
        self.profit_update_callback = None

    def initGatewaySettings(self):
        if self.fromGatewayName == "COINBENE":
            self.fromGateway = self.coinBeneGateway
            self.exchangeA2B = 0.99
            self.exchangeB2A = 0.99
        elif self.fromGatewayName == "Coinw":
            self.fromGateway = self.coinwGateway
            self.exchangeA2B = 0.99
            self.exchangeB2A = 0.99

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
            self.initGatewaySettings()

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

    def profit_calculate(self):
        key_from_0 = self.fromGatewayName + '.' + self.CURRENCY_SYMBOLS_A[0]
        key_from_1 = self.fromGatewayName + '.' + self.CURRENCY_SYMBOLS_A[1]
        key_jcc_0 = 'JCC.' + self.CURRENCY_SYMBOLS_B[0]
        key_jcc_1 = 'JCC.' + self.CURRENCY_SYMBOLS_B[1]
        key_profit_token = 'PROFIT_TOKEN'
        key_profit_cash = 'PROFIT_CASH'
        if self.CURRENCY_SYMBOLS_A[0] in self.fromGateway.accountDict and self.CURRENCY_SYMBOLS_A[1] in self.fromGateway.accountDict\
                and self.CURRENCY_SYMBOLS_B[0] in self.jccGateway.accountDict and self.CURRENCY_SYMBOLS_B[1] in self.jccGateway.accountDict:
            balance_from_0 = self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[0]].balance
            balance_from_1 = self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[1]].balance
            balance_jcc_0 = self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[0]].balance
            balance_jcc_1 = self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[1]].balance
        else:
            return
        if self.accountInfo.get(key_from_0) is None or self.accountInfo.get(key_from_1) is None\
                or self.accountInfo.get(key_jcc_0) is None or self.accountInfo.get(key_jcc_1) is None:
            self.accountInfo[key_from_0] = [balance_from_0, balance_from_0]
            self.accountInfo[key_from_1] = [balance_from_1, balance_from_1]
            self.accountInfo[key_jcc_0] = [balance_jcc_0, balance_jcc_0]
            self.accountInfo[key_jcc_1] = [balance_jcc_1, balance_jcc_1]
        self.accountInfo[key_from_0][1] = balance_from_0
        self.accountInfo[key_from_1][1] = balance_from_1
        self.accountInfo[key_jcc_0][1] = balance_jcc_0
        self.accountInfo[key_jcc_1][1] = balance_jcc_1
        self.accountInfo[key_profit_token] = self.accountInfo[key_from_0][1] - self.accountInfo[key_from_0][0] + self.accountInfo[key_jcc_0][1] - self.accountInfo[key_jcc_0][0]
        self.accountInfo[key_profit_cash] = self.accountInfo[key_from_1][1] - self.accountInfo[key_from_1][0] + (self.accountInfo[key_jcc_1][1] - self.accountInfo[key_jcc_1][0]) * self.exchangeA2B
        if self.profit_update_callback is not None:
            self.profit_update_callback(self.accountInfo)

    def registProfitCallback(self, callback):
        self.profit_update_callback = callback

    def startTrade(self):
        print('call starttrade')
        self.marketInfo = {}
        self.stage = 0
        self.registerEvent()
        self.profit_calculate()
        # 启动搬砖算法
        while self.active:
            self.jccGateway.exchangeApi.queryAccount()
            self.jccGateway.subscribe(None)
            self.jccGateway.exchangeApi.queryHistoryOrder()
            self.fromGateway.restApi.queryAccount()
            self.fromGateway.subscribe(None)
            self.profit_calculate()
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
            "bid1":float(tick.bidPrice1),
            "bid2": float(tick.bidPrice2),
            "bid3": float(tick.bidPrice3),
            "bid4": float(tick.bidPrice4),
            "bid5": float(tick.bidPrice5),
            "bidVolume":float(tick.bidVolume1),
            "bidVolume1":float(tick.bidVolume1),
            "bidVolume2": float(tick.bidVolume2),
            "bidVolume3": float(tick.bidVolume3),
            "bidVolume4": float(tick.bidVolume4),
            "bidVolume5": float(tick.bidVolume5),
            "ask":float(tick.askPrice1),
            "ask1":float(tick.askPrice1),
            "ask2": float(tick.askPrice2),
            "ask3": float(tick.askPrice3),
            "ask4": float(tick.askPrice4),
            "ask5": float(tick.askPrice5),
            "askVolume": float(tick.askVolume1),
            "askVolume1": float(tick.askVolume1),
            "askVolume2": float(tick.askVolume2),
            "askVolume3": float(tick.askVolume3),
            "askVolume4": float(tick.askVolume4),
            "askVolume5": float(tick.askVolume5),
        }
        if tick.vtSymbol == self.VT_SYMBOL_A:
            self.ticked_a = True
        elif tick.vtSymbol == self.VT_SYMBOL_B:
            self.ticked_b = True
        if self.ticked_a and self.ticked_b:
            self.seekBrickGap()
            self.ticked_a = False
            self.ticked_b = False

    def seekBrickGap(self):
        if self.marketInfo.get(self.VT_SYMBOL_B) is not None and self.marketInfo.get(self.VT_SYMBOL_A) is not None:
            gap = (self.marketInfo[self.VT_SYMBOL_B]["bid"] * self.exchangeA2B) / self.marketInfo[self.VT_SYMBOL_A]["ask"] - 1
            if False and gap > self.settingsDict["gapLimit"]:
                print((self.CURRENCY_SYMBOLS_A[0] + ": JCC BID:%f\t" + self.fromGatewayName + " ASK:%f\t Gap: %f") % (self.marketInfo[self.VT_SYMBOL_B]["bid"], self.marketInfo[self.VT_SYMBOL_A]["ask"], gap))
                usdt_amount = self.settingsDict["amount"] * self.marketInfo[self.VT_SYMBOL_B]["bid"] * self.exchangeA2B
                if self.stage == 0 and self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[0]].available >= self.settingsDict["amount"] and \
                        self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[1]].available > usdt_amount and \
                        self.marketInfo[self.VT_SYMBOL_B]["bidVolume"] >= self.settingsDict["amount"] and self.marketInfo[self.VT_SYMBOL_A]["askVolume"] >= self.settingsDict["amount"]:
                    self.stage = 1
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"] * self.marketInfo[self.VT_SYMBOL_B]["bid"]
                    orderReq.currencyGet = self.CURRENCY_SYMBOLS_B[1]
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.currencyPay = self.CURRENCY_SYMBOLS_B[0]
                    orderReq.direction = DIRECTION_SELL
                    orderReq.symbol = self.SYMBOL_B
                    orderReq.volume = self.settingsDict["amount"]
                    orderReq.price = self.marketInfo[self.VT_SYMBOL_B]["bid"]
                    self.writeLog(u'被动搬砖挂单：%s, 单价：%.4f, 数量：%.2f' % (orderReq.symbol, self.marketInfo[self.VT_SYMBOL_B]["bid"], orderReq.volume))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        orderReq = VtOrderReq()
                        orderReq.price = self.marketInfo[self.VT_SYMBOL_A]["ask"]
                        orderReq.volume = self.settingsDict["amount"]  # 交易数量
                        orderReq.symbol = self.SYMBOL_A  # 交易对
                        orderReq.direction = DIRECTION_BUY  # 限价买入
                        self.writeLog(
                            u'对冲挂单：%s, 单价：%.4f, 数量：%.2f' % (orderReq.symbol, self.marketInfo[self.VT_SYMBOL_A]["ask"], orderReq.volume))

                        def on_order_fallback2():
                            self.fromGateway.sendOrder(orderReq)
                        self.onOrderFallback = on_order_fallback2

                        def on_order_filled2(order2):
                            if order2.status == STATUS_ALLTRADED or order2.status == STATUS_PARTTRADED_CANCEL or order2.status == STATUS_CANCELLED:
                                self.stage = 0
                        self.onOrderFilled = on_order_filled2
                        self.fromGateway.sendOrder(orderReq)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
            gap = self.marketInfo[self.VT_SYMBOL_A]["bid"] / (self.marketInfo[self.VT_SYMBOL_B]["ask"] / self.exchangeB2A) - 1
            if False and gap > self.settingsDict["gapLimit"]:
                print((self.CURRENCY_SYMBOLS_A[0] + ": " + self.fromGatewayName + " BID:%f\tJCC ASK:%f\t Gap: %f") % (self.marketInfo[self.VT_SYMBOL_A]["bid"], self.marketInfo[self.VT_SYMBOL_B]["ask"], gap))
                cny_amount = self.settingsDict["amount"] * self.marketInfo[self.VT_SYMBOL_B]["ask"]
                if self.stage == 0 and self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[1]].available >= cny_amount and \
                        self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[0]].available > self.settingsDict["amount"] and \
                        self.marketInfo[self.VT_SYMBOL_B]["askVolume"] >= self.settingsDict["amount"] and self.marketInfo[self.VT_SYMBOL_A]["bidVolume"] >= self.settingsDict["amount"]:
                    self.stage = 2
                    orderReq = VtOrderReq()
                    orderReq.valueGet = self.settingsDict["amount"]
                    orderReq.currencyGet = self.CURRENCY_SYMBOLS_B[0]
                    orderReq.valuePay = round(self.settingsDict["amount"] * self.marketInfo[self.VT_SYMBOL_B]["ask"], 6)
                    orderReq.currencyPay = self.CURRENCY_SYMBOLS_B[1]
                    orderReq.direction = DIRECTION_BUY
                    orderReq.symbol = self.SYMBOL_B
                    orderReq.volume = self.settingsDict["amount"]
                    orderReq.price = self.marketInfo[self.VT_SYMBOL_B]["ask"]
                    self.writeLog(u'被动搬砖挂单：%s, 单价：%.4f, 数量：%.2f' % (orderReq.symbol, self.marketInfo[self.VT_SYMBOL_B]["ask"], orderReq.volume))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        orderReq = VtOrderReq()
                        orderReq.price = self.marketInfo[self.VT_SYMBOL_A]["bid"]
                        orderReq.volume = self.settingsDict["amount"]  # 交易数量
                        orderReq.symbol = self.SYMBOL_A  # 交易对
                        orderReq.direction = DIRECTION_SELL  # 限价卖出
                        self.writeLog(u'对冲挂单：%s, 单价：%.4f, 数量：%.2f' % (orderReq.symbol, self.marketInfo[self.VT_SYMBOL_A]["bid"], orderReq.volume))

                        def on_order_fallback2():
                            self.fromGateway.sendOrder(orderReq)
                        self.onOrderFallback = on_order_fallback2

                        def on_order_filled2(order2):
                            if order2.status == STATUS_ALLTRADED or order2.status == STATUS_PARTTRADED_CANCEL or order2.status == STATUS_CANCELLED:
                                self.stage = 0
                        self.onOrderFilled = on_order_filled2
                        self.fromGateway.sendOrder(orderReq)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
            if self.stage == 0:
                price_with_gap = self.calc_price_with_gap("bid", self.settingsDict["amount"]) * self.exchangeA2B
                if price_with_gap > self.marketInfo[self.VT_SYMBOL_B]["bid"] + self.settingsDict['step'] and self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[0]].available >= self.settingsDict["amount"] and \
                        self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[1]].available >= self.settingsDict["amount"] * self.marketInfo[self.VT_SYMBOL_B]["bid"]:
                    price = round(self.marketInfo[self.VT_SYMBOL_B]["bid"] + self.settingsDict['step'], self.settingsDict['precision'])
                    if price > self.marketInfo[self.VT_SYMBOL_B]["ask"]:
                        price = self.marketInfo[self.VT_SYMBOL_B]["ask"]
                    gap = self.calc_price_with_gap("bid", self.settingsDict["amount"]) * self.exchangeA2B / price - 1
                    print((self.CURRENCY_SYMBOLS_A[0] + ": JCC BID:%f\t" + self.fromGatewayName + " BID:%f\t Gap: %f") % (price, price_with_gap, gap))
                    self.stage = 3
                    orderReq = VtOrderReq()
                    orderReq.currencyGet = self.CURRENCY_SYMBOLS_B[0]
                    orderReq.valueGet = price * self.settingsDict["amount"]
                    orderReq.currencyPay = self.CURRENCY_SYMBOLS_B[1]
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.direction = DIRECTION_BUY
                    orderReq.symbol = self.SYMBOL_B
                    orderReq.volume = self.settingsDict["amount"]
                    orderReq.price = price
                    self.writeLog(u'被动搬砖买一盘口挂单：%s, 单价：%.6f, 数量：%.2f' % (orderReq.symbol, price, orderReq.volume))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        def trade_logic(order2):
                            orderReq2 = VtOrderReq()
                            if self.marketInfo[self.VT_SYMBOL_A]['bidVolume'] >= order.tradedVolume:
                                orderReq2.price = self.marketInfo[self.VT_SYMBOL_A]["bid"]
                            else:
                                orderReq2.price = self.marketInfo[self.VT_SYMBOL_A]["bid2"]
                            orderReq2.volume = order.tradedVolume  # 交易数量
                            orderReq2.symbol = self.SYMBOL_A  # 交易对
                            orderReq2.direction = DIRECTION_SELL  # 限价卖出
                            self.writeLog(
                                u'被动搬砖对冲挂单：%s, 单价：%.6f, 数量：%.2f' % (orderReq.symbol, orderReq2.price, orderReq2.volume))
                            self.stage = 4

                            def on_order_fallback2():
                                self.fromGateway.sendOrder(orderReq2)

                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order3):
                                if order3.status == STATUS_ALLTRADED:
                                    self.stage = 0

                            self.onOrderFilled = on_order_filled2
                            self.fromGateway.sendOrder(orderReq2)

                        if order.status == STATUS_PARTTRADED and order.tradedVolume >= 1 and not self.brickMap[order.vtOrderID]['cancelling']:
                            self.brickMap[order.vtOrderID]['cancelling'] = True
                            self.jccGateway.cancelOrder(order)
                        elif order.status == STATUS_ALLTRADED or order.status == STATUS_PARTTRADED_CANCEL:
                            trade_logic(order)
                        elif order.tradedVolume >= 1 and order.status == STATUS_CANCELLED:
                            trade_logic(order)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
                price_with_gap = self.calc_price_with_gap("ask", self.settingsDict["amount"]) / self.exchangeB2A
                cny_amount = self.settingsDict["amount"] * self.calc_price_with_gap("ask", self.settingsDict["amount"])
                if price_with_gap < self.marketInfo[self.VT_SYMBOL_B]["ask"] - self.settingsDict['step'] and self.fromGateway.accountDict[self.CURRENCY_SYMBOLS_A[1]].available >= cny_amount and \
                        self.jccGateway.accountDict[self.CURRENCY_SYMBOLS_B[0]].available >= self.settingsDict["amount"]:
                    price = round(self.marketInfo[self.VT_SYMBOL_B]["ask"] - self.settingsDict['step'], self.settingsDict['precision'])
                    if price < self.marketInfo[self.VT_SYMBOL_B]["bid"]:
                        price = self.marketInfo[self.VT_SYMBOL_B]["bid"]
                    gap = price / self.marketInfo[self.VT_SYMBOL_A]["ask"] - 1
                    print((self.CURRENCY_SYMBOLS_A[0] + ": JCC ASK:%f\t" + self.fromGatewayName + " ASK:%f\t Gap: %f") % (self.marketInfo[self.VT_SYMBOL_B]["ask"], price_with_gap, gap))
                    self.stage = 5
                    orderReq = VtOrderReq()
                    orderReq.valueGet = round(price * self.settingsDict["amount"], 6)
                    orderReq.currencyGet = self.CURRENCY_SYMBOLS_B[1]
                    orderReq.valuePay = self.settingsDict["amount"]
                    orderReq.currencyPay = self.CURRENCY_SYMBOLS_B[0]
                    orderReq.price = price
                    orderReq.volume = self.settingsDict["amount"]  # 交易数量
                    orderReq.symbol = self.SYMBOL_B  # 交易对
                    orderReq.direction = DIRECTION_SELL  # 限价卖出
                    self.writeLog(u'被动搬砖卖一盘口挂单：%s, 单价：%.6f, 数量：%.2f' % (orderReq.symbol, price, orderReq.volume))

                    def on_order_fallback():
                        self.stage = 0
                    self.onOrderFallback = on_order_fallback

                    def on_order_filled(order):
                        def trade_logic(order2):
                            orderReq2 = VtOrderReq()
                            if self.marketInfo[self.VT_SYMBOL_A]['askVolume'] >= order.tradedVolume:
                                orderReq2.price = self.marketInfo[self.VT_SYMBOL_A]["ask"]
                            else:
                                orderReq2.price = self.marketInfo[self.VT_SYMBOL_A["ask2"]]
                            orderReq2.direction = DIRECTION_BUY
                            orderReq2.symbol = self.SYMBOL_A
                            orderReq2.volume = order2.tradedVolume
                            self.writeLog(u'被动搬砖对冲挂单：%s, 单价：%.6f, 数量：%.2f' % (orderReq2.symbol, orderReq2.price, orderReq2.volume))
                            self.stage = 6

                            def on_order_fallback2():
                                self.fromGateway.sendOrder(orderReq2)
                            self.onOrderFallback = on_order_fallback2

                            def on_order_filled2(order3):
                                if order3.status == STATUS_ALLTRADED:
                                    self.stage = 0
                            self.onOrderFilled = on_order_filled2
                            self.fromGateway.sendOrder(orderReq2)

                        if order.status == STATUS_PARTTRADED and order.tradedVolume >= 1 and not self.brickMap[order.vtOrderID]['cancelling']:
                            self.brickMap[order.vtOrderID]['cancelling'] = True
                            self.jccGateway.cancelOrder(order)
                        elif order.status == STATUS_ALLTRADED or order.status == STATUS_PARTTRADED_CANCEL:
                            trade_logic(order)
                        elif order.tradedVolume >= 1 and order.status == STATUS_CANCELLED:
                            trade_logic(order)
                    self.onOrderFilled = on_order_filled
                    self.jccGateway.sendOrder(orderReq)
            if self.stage == 3:
                for vtOrderId in self.brickMap:
                    if vtOrderId.startswith("JCC.") and self.brickMap[vtOrderId]['status'] == 'ordered':
                        price_with_gap = self.calc_price_with_gap("bid", self.brickMap[vtOrderId]['order'].volume) * self.exchangeA2B
                        price = self.brickMap[vtOrderId]['order'].price
                        if round(price_with_gap, self.settingsDict['precision']) < price and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        elif price < round(self.marketInfo[self.VT_SYMBOL_B]["bid"], self.settingsDict['precision']) < round(price_with_gap, self.settingsDict['precision']) \
                                and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        elif round(price - self.marketInfo[self.VT_SYMBOL_B]["bid"], self.settingsDict['precision']) == 0 and round(price - self.marketInfo[self.VT_SYMBOL_B]["bid2"], self.settingsDict['precision']) > self.settingsDict['step'] and self.marketInfo[self.VT_SYMBOL_B]["bidVolume"] == self.brickMap[vtOrderId]['order'].volume\
                                and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    if price - round(self.marketInfo[self.VT_SYMBOL_B]["bid"], self.settingsDict['precision']) < self.settingsDict['step']:
                                        self.marketInfo[self.VT_SYMBOL_B]["bid"] = self.marketInfo[self.VT_SYMBOL_B]["bid2"]
                                        self.marketInfo[self.VT_SYMBOL_B]["bidVolume"] = self.marketInfo[self.VT_SYMBOL_B]["bidVolume2"]
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])

            if self.stage == 5:
                for vtOrderId in self.brickMap:
                    if vtOrderId.startswith("JCC.") and self.brickMap[vtOrderId]['status'] == 'ordered':
                        price_with_gap = self.calc_price_with_gap("ask", self.brickMap[vtOrderId]['order'].volume) / self.exchangeB2A
                        price = self.brickMap[vtOrderId]['order'].price
                        if round(price_with_gap, self.settingsDict['precision']) > price and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        elif price > round(self.marketInfo[self.VT_SYMBOL_B]["ask"], self.settingsDict['precision']) > round(price_with_gap, self.settingsDict['precision']) \
                                and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])
                        elif round(self.marketInfo[self.VT_SYMBOL_B]["ask"] - price, self.settingsDict['precision']) == 0 and round(self.marketInfo[self.VT_SYMBOL_B]["ask2"] - price, self.settingsDict['precision']) > self.settingsDict['step'] and self.marketInfo[self.VT_SYMBOL_B]["askVolume"] == self.brickMap[vtOrderId]['order'].volume\
                                and self.brickMap[vtOrderId]['nextCancelTime'] < time.time():
                            self.brickMap[vtOrderId]['nextCancelTime'] = time.time() + 10
                            self.writeLog(u'被动搬砖盘口撤单：%s, 单价：%.6f' % (self.brickMap[vtOrderId]['order'].symbol, price))

                            def order_cancelled(order):
                                if order.orderID == self.brickMap[vtOrderId]['order'].orderID:
                                    if price - round(self.marketInfo[self.VT_SYMBOL_B]["ask"], self.settingsDict['precision']) < self.settingsDict['step']:
                                        self.marketInfo[self.VT_SYMBOL_B]["ask"] = self.marketInfo[self.VT_SYMBOL_B]["ask2"]
                                        self.marketInfo[self.VT_SYMBOL_B]["askVolume"] = self.marketInfo[self.VT_SYMBOL_B]["askVolume2"]
                                    self.stage = 0
                            self.onOrderCancelled = order_cancelled
                            self.jccGateway.cancelOrder(self.brickMap[vtOrderId]['order'])

        pass

    def calc_price_with_gap(self, direction, target_volume):
        fill_volume = 0
        fill_amount = 0
        for i in range(1, 6):
            volume = self.marketInfo[self.VT_SYMBOL_A]["%sVolume%d" % (direction, i)]
            price = self.marketInfo[self.VT_SYMBOL_A]["%s%d" % (direction, i)]
            if fill_volume + volume < target_volume:
                fill_amount += price * volume
                fill_volume += volume
            else:
                fill_amount += price * (target_volume - fill_volume)
                fill_volume = target_volume
                break
        if direction == 'bid':
            return (1 - self.settingsDict["gapLimit"]) * (fill_amount / fill_volume)
        else:
            return (1 + self.settingsDict["gapLimit"]) * (fill_amount / fill_volume)

    # 停止搬砖交易
    def stopTrade(self):
        self.unregisterEvent()
        self.cancelAll()

    def cancelAll(self):
        """撤销所有委托"""
        if hasattr(self.fromGateway, 'cancelAllOrders'):
            self.fromGateway.cancelAllOrders()
        if hasattr(self.jccGateway, 'cancelAllOrders'):
            self.jccGateway.cancelAllOrders()

    #----------------------------------------------------------------------
    def updateOrder(self, event):
        #更新下单数据
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return
        order = event.dict_['data']
        if order.status == STATUS_CANCELLED:
            if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                self.brickMap[order.vtOrderID]['watchStatus'] = False
                self.brickMap[order.vtOrderID]['order'] = order
                self.brickMap[order.vtOrderID]['status'] = 'canceled'
                if self.brickMap[order.vtOrderID]['cancelling'] and self.onOrderFilled is not None:
                    self.onOrderFilled(order)
                elif self.onOrderCancelled is not None:
                    self.onOrderCancelled(order)
            elif order.vtSymbol == self.VT_SYMBOL_B:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['status'] != 'canceled':
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'canceled'
                    if self.brickMap[order.vtOrderID]['cancelling'] and self.onOrderFilled is not None:
                        self.onOrderFilled(order)
                    elif self.onOrderCancelled is not None:
                        self.onOrderCancelled(order)
        if order.status == STATUS_ORDERED:
            self.onOrderFallback = None
            if order.vtSymbol == self.VT_SYMBOL_A:
                watchThread = Thread(target=self.watchCoinBeneOrder, args=(order.orderID, order.vtOrderID))
                self.brickMap[order.vtOrderID] = {
                    'order': order,
                    'status': 'ordered',
                    'cancelling': False,
                    'watchThread': watchThread,
                    'watchStatus': True,
                    'nextCancelTime': 0
                }
                watchThread.start()
                # self.stage = 0
            elif order.vtSymbol == self.VT_SYMBOL_B:
                self.brickMap[order.vtOrderID] = {
                    'order': order,
                    'cancelling': False,
                    'status': 'ordered',
                    'nextCancelTime': 0
                }
                pass
        elif order.status == STATUS_ALLTRADED:
            if order.vtSymbol == self.VT_SYMBOL_A:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                    self.brickMap[order.vtOrderID]['watchStatus'] = False
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'filled'
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
            elif order.vtSymbol == self.VT_SYMBOL_B:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['status'] == 'ordered':
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'filled'
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
        elif order.status == STATUS_PARTTRADED:
            if order.vtSymbol == self.VT_SYMBOL_A:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'partfilled'
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
            elif order.vtSymbol == self.VT_SYMBOL_B:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['status'] == 'ordered':
                    self.brickMap[order.vtOrderID]['order'] = order
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
        elif order.status == STATUS_PARTTRADED_CANCEL:
            if order.vtSymbol == self.VT_SYMBOL_A:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['watchStatus']:
                    self.brickMap[order.vtOrderID]['watchStatus'] = False
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'partfilled'
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)
            elif order.vtSymbol == self.VT_SYMBOL_B:
                if order.vtOrderID in self.brickMap.keys() and self.brickMap[order.vtOrderID]['status'] != 'partfilled':
                    self.brickMap[order.vtOrderID]['order'] = order
                    self.brickMap[order.vtOrderID]['status'] = 'partfilled'
                    if self.onOrderFilled is not None:
                        self.onOrderFilled(order)

        elif order.status == STATUS_REJECTED:
            if self.onOrderFallback is not None:
                self.onOrderFallback()

    def watchCoinBeneOrder(self, order_id, vt_order_id):
        while self.brickMap[vt_order_id]['watchStatus'] and self.active:
            self.fromGateway.queryOrder(order_id)
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
            self.loadSetting()
            self.reqThread = Thread(target=self.startTrade)
            self.reqThread.start()
            #self.startTrade()
        else:
            self.writeLog(u'搬砖功能停止')

            self.stopTrade()
            
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        pass


