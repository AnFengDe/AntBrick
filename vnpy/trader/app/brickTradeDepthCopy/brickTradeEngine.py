# encoding: UTF-8

'''
本文件中实现了搬砖引擎
'''

from __future__ import division

import json
import os
import platform
import threading
import time
from datetime import datetime, timedelta
import random
from itertools import cycle, islice
from threading import Thread

from vnpy.event import Event
from vnpy.trader.vtEvent import *
from vnpy.trader.vtConstant import *
from vnpy.trader.vtGateway import VtLogData, VtAccountData, VtOrderData
from vnpy.trader.vtFunction import getJsonPath
from vnpy.trader.vtObject import VtOrderReq

########################################################################
class BrickTradeEngine(object):
    """搬砖引擎"""
    settingFileName = 'brickTradeDepthCopy_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    name = u'深度复制搬砖模块'

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
        self.huobiGatewayName = 'HUOBI'
        self.huobiGateway = self.mainEngine.getGateway(self.huobiGatewayName)
        self.jccGatewayName = 'JCC'
        self.jccGateway = self.mainEngine.getGateway(self.jccGatewayName)
        self.marketInfo = {}
        self.accountDict = {}
        self.accountDictLast = {}
        self.stage = 0

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
        self.orderManager = OrderManager()
        self.latestReq = None
        self.jccLatestOperateTime = time.time() - 10


    def initGatewaySettings(self):
        if self.fromGatewayName == "HUOBI":
            self.fromGateway = self.huobiGateway
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
            # self.fromGateway.subscribe(None)
            # self.fromGateway.restApi.queryAccount()
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
        self.seekBrickGap()

    def seekBrickGap(self):
        target_buy_depth = {}
        if self.VT_SYMBOL_A not in self.marketInfo.keys():
            return
        for i in range(1, 6):
            price = self.marketInfo[self.VT_SYMBOL_A]["bid%d" % i] * (1 - self.settingsDict['gapLimit'])
            target_buy_depth[self.orderManager.formatPrice(price, DIRECTION_BUY)] = {
                "volumeL": int(self.marketInfo[self.VT_SYMBOL_A]["bidVolume%d" % i] * self.settingsDict["mapWeightL"][i - 1]),
                "volumeH": int(self.marketInfo[self.VT_SYMBOL_A]["bidVolume%d" % i] * self.settingsDict["mapWeightH"][i - 1]),
                "volume": int(self.marketInfo[self.VT_SYMBOL_A]["bidVolume%d" % i] * self.settingsDict["mapWeight"][i - 1])
            }
        target_sell_depth = {}
        for i in range(1, 6):
            price = self.marketInfo[self.VT_SYMBOL_A]["ask%d" % i] * (1 + self.settingsDict['gapLimit'])
            target_sell_depth[self.orderManager.formatPrice(price, DIRECTION_BUY)] = {
                "volumeL": int(self.marketInfo[self.VT_SYMBOL_A]["askVolume%d" % i] * self.settingsDict["mapWeightL"][i - 1]),
                "volumeH": int(self.marketInfo[self.VT_SYMBOL_A]["askVolume%d" % i] * self.settingsDict["mapWeightH"][i - 1]),
                "volume": int(self.marketInfo[self.VT_SYMBOL_A]["askVolume%d" % i] * self.settingsDict["mapWeight"][i - 1])
            }
        operations = self.orderManager.difference((target_buy_depth, target_sell_depth))
        if len(operations) > 0:
            print("待处理", operations)
            if self.jccLatestOperateTime > time.time():
                return
            for operation in operations:
                if operation['op'] == 'cancel':
                    print("撤%s单: 价格 %s\t数量 %f" % (self.orderManager.orderBook[operation['order_id']].direction, self.orderManager.orderBook[operation['order_id']].price, self.orderManager.orderBook[operation['order_id']].volume))
                    self.jccGateway.cancelOrder(int(operation['order_id'].split('.')[1]))
                    self.jccLatestOperateTime = time.time() + 10
                    break
                elif int(operation['volume']) > 0 and not self.latestReq:
                    req = VtOrderReq()
                    req.symbol = self.SYMBOL_B
                    req.volume = int(operation['volume'])
                    req.price = float(operation['price'])
                    req.direction = operation['op']
                    if req.direction == DIRECTION_BUY:
                        req.currencyGet = self.CURRENCY_SYMBOLS_B[0]
                        req.currencyPay = self.CURRENCY_SYMBOLS_B[1]
                        req.valueGet = req.volume
                        req.valuePay = round(req.volume * req.price, 6)
                    else:
                        req.currencyGet = self.CURRENCY_SYMBOLS_B[1]
                        req.currencyPay = self.CURRENCY_SYMBOLS_B[0]
                        req.valueGet = round(req.volume * req.price, 6)
                        req.valuePay = req.volume
                    if req.valuePay > self.jccGateway.accountDict[req.currencyPay].available:
                        continue
                    print("挂%s单: 价格 %s\t数量 %d" % (operation['op'], operation['price'], int(operation['volume'])))
                    self.latestReq = self.jccGateway.sendOrder(req)
                    self.jccLatestOperateTime = time.time() + 10
                    break

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

    def onOrderFilled(self, order):
        if order.tradedVolume > 0:
            req = VtOrderReq()
            req.symbol = self.SYMBOL_A
            req.volume = order.tradedVolume
            if order.direction == DIRECTION_BUY:
                req.direction = DIRECTION_SELL
                req.price = round(order.price / (1 + self.settingsDict['gapLimit']), 4)
            else:
                req.direction = DIRECTION_BUY
                req.price = round(order.price / (1 - self.settingsDict['gapLimit']), 4)
            self.writeLog("对冲挂%s单: 数量 %f\t价格 %f" % (req.direction, req.volume, req.price))
            self.fromGateway.sendOrder(req)

    #----------------------------------------------------------------------
    def updateOrder(self, event):
        #更新下单数据
        tick = event.dict_['data']
        if tick.vtSymbol not in self.settingsDict["vtSymbols"]:
            return
        order = event.dict_['data']
        if order.status == STATUS_CANCELLED:
            if order.vtSymbol == self.VT_SYMBOL_B and self.orderManager.onOrder(order):
                self.onOrderFilled(order)
        if order.status == STATUS_ORDERED:
            if order.vtSymbol == self.VT_SYMBOL_B:
                self.orderManager.onOrder(order)
        elif order.status == STATUS_ALLTRADED:
            if order.vtSymbol == self.VT_SYMBOL_B and self.orderManager.onOrder(order):
                self.onOrderFilled(order)
        elif order.status == STATUS_PARTTRADED:
            if order.vtSymbol == self.VT_SYMBOL_B:
                self.orderManager.onOrder(order)
                if order.tradedVolume * order.price > 1:
                    self.jccGateway.cancelOrder(order.orderID)
        elif order.status == STATUS_PARTTRADED_CANCEL:
            if order.vtSymbol == self.VT_SYMBOL_B and self.orderManager.onOrder(order):
                self.onOrderFilled(order)
        elif order.status == STATUS_REJECTED:
            pass
        if self.latestReq == order.vtOrderID:
            self.latestReq = ""

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


class OrderManager(object):
    def __init__(self):
        self.orderBook = {}
        self.lock = threading.Lock()

    def __difference(self, order_depth, target_depth, direction):
        order_depth_keys = set(order_depth.keys())
        none_exist_prices = order_depth_keys.difference(target_depth.keys())
        operations_cancel = []
        operations_order = []
        for depth in sorted(none_exist_prices, reverse=True) if direction == DIRECTION_BUY else sorted(none_exist_prices):
            for vtOrderId in order_depth[depth]["orders"]:
                operations_cancel.append({"op": "cancel", "order_id": vtOrderId})
        exist_prices = order_depth_keys.intersection(target_depth.keys())
        for depth in sorted(exist_prices):
            deltaH = target_depth[depth]['volumeH'] - order_depth[depth]['volume']
            deltaL = target_depth[depth]['volumeL'] - order_depth[depth]['volume']
            delta = target_depth[depth]['volume'] - order_depth[depth]['volume']
            if deltaL > 0:
                operations_order.append({"op": direction, "volume": delta, "price": depth})
            elif deltaH < 0:
                for vtOrderId in reversed(order_depth[depth]["orders"]):
                    operations_cancel.append({"op": "cancel", "order_id": vtOrderId})
                    deltaH += self.orderBook[vtOrderId].volume - self.orderBook[vtOrderId].tradedVolume
                    if deltaH >= 0:
                        break
        new_prices = set(target_depth.keys()).difference(order_depth_keys)
        for depth in sorted(new_prices) if direction == DIRECTION_BUY else sorted(new_prices, reverse=True):
            if target_depth[depth]["volume"] >= 1:
                operations_order.append({"op": direction, "volume": target_depth[depth]["volume"], "price": depth})
        return operations_cancel, operations_order

    def xmerge(self, a, b):
        alen, blen = len(a), len(b)
        mlen = min(alen, blen)
        for i in range(mlen):
            yield a[i]
            yield b[i]

        if alen > blen:
            for i in range(mlen, alen):
                yield a[i]
        else:
            for i in range(mlen, blen):
                yield b[i]

    def difference(self, target_depth):
        order_depth = self.getPriceDepth()
        operations = []
        operations_cancel, operations_order_buy = self.__difference(order_depth[0], target_depth[0], DIRECTION_BUY)
        operations.extend(operations_cancel)
        operations_cancel, operations_order_sell = self.__difference(order_depth[1], target_depth[1], DIRECTION_SELL)
        operations.extend(operations_cancel)
        if len(operations_order_buy) > len(operations_order_sell):
            operations.extend(self.xmerge(operations_order_buy, operations_order_sell))
        else:
            operations.extend(self.xmerge(operations_order_sell, operations_order_buy))
        return operations

    def formatPrice(self, price, direction, precision=3):
        from decimal import Decimal, ROUND_UP, ROUND_DOWN
        if direction == DIRECTION_BUY:
            return str(Decimal(price).quantize(Decimal('0.' + '0' * precision), ROUND_UP))
        else:
            return str(Decimal(price).quantize(Decimal('0.' + '0' * precision), ROUND_DOWN))

    def getPriceDepth(self, precision=3):
        buy_depth = {}
        sell_depth = {}
        self.lock.acquire()
        try:
            for vtOrderId in self.orderBook:
                order = self.orderBook[vtOrderId]
                price_display = self.formatPrice(order.price, order.direction)
                if order.direction == DIRECTION_BUY:
                    if price_display in buy_depth:
                        buy_depth[price_display]['volume'] += order.volume - order.tradedVolume
                        buy_depth[price_display]['orders'].append(order.vtOrderID)
                    else:
                        buy_depth[price_display] = {'volume': order.volume - order.tradedVolume, 'orders': [order.vtOrderID]}
                else:
                    if price_display in sell_depth:
                        sell_depth[price_display]['volume'] += order.volume - order.tradedVolume
                        sell_depth[price_display]['orders'].append(order.vtOrderID)
                    else:
                        sell_depth[price_display] = {'volume': order.volume - order.tradedVolume, 'orders': [order.vtOrderID]}
        finally:
            self.lock.release()
            return buy_depth, sell_depth

    def onOrder(self, order):
        self.lock.acquire()
        try:
            if order.status == STATUS_ORDERED:
                if order.vtOrderID not in self.orderBook:
                    self.orderBook[order.vtOrderID] = order
                    return True
                return False
            elif order.status == STATUS_CANCELLED:
                if order.vtOrderID in self.orderBook:
                    self.orderBook.pop(order.vtOrderID, '^.^')
                    return True
                return False
            elif order.status == STATUS_ALLTRADED:
                if order.vtOrderID in self.orderBook:
                    self.orderBook.pop(order.vtOrderID, '^.^')
                    return True
                return False
            elif order.status == STATUS_PARTTRADED:
                if order.vtOrderID in self.orderBook:
                    self.orderBook[order.vtOrderID] = order
                    return True
                return False
            elif order.status == STATUS_PARTTRADED_CANCEL:
                if order.vtOrderID in self.orderBook:
                    self.orderBook.pop(order.vtOrderID, '^.^')
                    return True
                return False
        finally:
            self.lock.release()

if __name__ == "__main__":
    mgr = OrderManager()
    req = VtOrderData()
    req.vtOrderID = '1'
    req.volume = 10
    req.price = 5.6
    req.direction = DIRECTION_BUY
    req.status = STATUS_ORDERED
    mgr.onOrder(req)
    req = VtOrderData()
    req.vtOrderID = '2'
    req.volume = 10
    req.price = 5.5
    req.direction = DIRECTION_BUY
    req.status = STATUS_ORDERED
    mgr.onOrder(req)
    print(mgr.getPriceDepth())
    targetDepth = mgr.getPriceDepth()
    print(targetDepth)
    targetDepth[0]['5.7'] = {"volume": 10, "volumeH": 10, "volumeL": 10}
    targetDepth[1]['5.1'] = {"volume": 10, "volumeH": 10, "volumeL": 10}
    req = VtOrderData()
    req.vtOrderID = '4'
    req.volume = 20
    req.price = 5.5
    req.direction = DIRECTION_BUY
    req.status = STATUS_ORDERED
    mgr.onOrder(req)
    print(mgr.getPriceDepth())
    req = VtOrderData()
    req.vtOrderID = '3'
    req.volume = 15
    req.price = 5.2
    req.direction = DIRECTION_SELL
    req.status = STATUS_ORDERED
    mgr.onOrder(req)
    print(mgr.getPriceDepth())
    print(mgr.difference(targetDepth))

