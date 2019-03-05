# encoding: UTF-8

'''
Coinbene交易接口
'''
from __future__ import print_function

import json
import hashlib
import hmac
import sys
import base64
import zlib
from datetime import timedelta, datetime
from copy import copy

from vnpy.api.rest import RestClient, Request
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

#from threading import Thread

REST_HOST = 'http://api.coinbene.com'
EXCHANGE_COINBENE = "COINBENE"

# 内外盘
dealStatusMap = {}
dealStatusMap[TRADED_BUY] = 2   # 外盘
dealStatusMap[TRADED_SELL] = 1  # 内盘

# 委托状态类型映射
orderStatusMap = {}
orderStatusMap[STATUS_CANCELLED] = -2
orderStatusMap[STATUS_NOTVALID] = -1
orderStatusMap[STATUS_NOTTRADED] = 0
orderStatusMap[STATUS_PARTTRADED] = 1
orderStatusMap[STATUS_ALLTRADED] = 2
orderStatusMap[STATUS_ORDERED] = 3

# 方向和订单类型映射
directionMap = {}
directionMap[(DIRECTION_BUY)] = 0
directionMap[(DIRECTION_SELL)] = 1

orderTypeMap = {}
orderTypeMap[(PRICETYPE_MARKETPRICE)] = 0
orderTypeMap[(PRICETYPE_LIMITPRICE)] = 1

dealStatusMapReverse = {v: k for k, v in dealStatusMap.items()}
orderStatusMapReverse = {v: k for k, v in orderStatusMap.items()}
directionMapReverse = {v: k for k, v in directionMap.items()}
orderTypeMapReverse = {v: k for k, v in orderTypeMap.items()}

class CoinbeneGateway(VtGateway):
    """Coinbene接口"""

    # ----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName=''):
        """Constructor"""
        super().__init__(eventEngine, gatewayName)
        self.localID = 10000

        self.accountDict = {}
        self.orderDict = {}
        self.localOrderDict = {}
        #self.orderLocalDict = {}

        self.qryEnabled = False         # 是否要启动循环查询

        self.restApi = CoinbeneRestApi(self)

        self.fileName = 'GatewayConfig/' + self.gatewayName + '_connect.json'
        self.filePath = getJsonPath(self.fileName, __file__)
        #symbols_filepath = os.getcwd() + '\GatewayConfig' + '/' + self.fileName

    def connect(self):
        """连接"""
        try:
            f = open(self.filePath)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = '读取连接配置出错，请检查'
            self.onLog(log)
            return

        # 解析json文件
        setting = json.load(f)
        f.close()

        try:
            apiKey = str(setting['apiKey'])
            secretKey = str(setting['secretKey'])
            symbols = setting['symbols']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = '连接配置缺少字段，请检查'
            self.onLog(log)
            return

        # 创建行情和交易接口对象
        self.restApi.connect(apiKey, secretKey, symbols)

        # 初始化并启动查询
        #self.initQuery()

    def subscribe(self, subscribeReq):
        """订阅行情"""
        self.restApi.subscribe(subscribeReq)

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        self.restApi.sendOrder(orderReq)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.restApi.cancelOrder(cancelOrderReq)

    def cancelAllOrders(self):
        """全部撤单"""
        self.restApi.cancelAllOrders()

    # ----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.restApi.stop()

    # ----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            # 需要循环的查询函数列表
            self.qryFunctionList = [self.queryInfo]

            self.qryCount = 0  # 查询触发倒计时
            self.qryTrigger = 4  # 查询触发点
            self.qryNextFunction = 0  # 上次运行的查询函数索引

            self.startQuery()

    # ----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        self.qryCount += 1

        if self.qryCount > self.qryTrigger:
            # 清空倒计时
            self.qryCount = 0

            # 执行查询函数
            function = self.qryFunctionList[self.qryNextFunction]
            function()

            # 计算下次查询函数的索引，如果超过了列表长度，则重新设为0
            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0

    # ----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)

    # ----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled

    # ----------------------------------------------------------------------
    def queryInfo(self):
        """"""
        self.restApi.queryAccount()

    def processQueueOrder(self, data, historyFlag):
        for d in data['data']:
            # self.gateway.localID += 1
            # localID = str(self.gateway.localID)

            order = VtOrderData()
            order.gatewayName = self.gatewayName

            order.symbol = d['symbol']
            order.exchange = 'Coinbene'
            order.vtSymbol = '.'.join([order.exchange, order.symbol])

            order.orderID = d['orderid']
            # order.vtOrderID = '.'.join([self.gatewayName, localID])
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])

            order.price = float(d['price'])  # 委托价格
            order.avgprice = float(d['avgprice'])  # 平均成交价
            order.volume = float(d['amount']) + float(d['executedamount'])  # 委托数量
            order.tradedVolume = float(d['executedamount'])  # 成交数量
            order.status = orderStatusMapReverse[d['status']]  # 订单状态
            order.direction = directionMapReverse[d['side']]  # 交易方向   0 买入 1 卖出
            order.orderType = orderTypeMapReverse[d['type']]  # 订单类型  0	市场价  1	 限价

            dt = datetime.fromtimestamp(d['timestamp'])
            order.orderTime = dt.strftime('%Y-%m-%d %H:%M:%S')

            if order.status == STATUS_ALLTRADED:
                # order.vtTradeID =  '.'.join([self.gatewayName, order.orderID])
                if historyFlag:
                    self.onTrade(order)
                else:
                    self.onOrder(order)  # 普通推送更新委托列表
            else:
                self.onOrder(order)

    def writeLog(self, msg):
        """"""
        log = VtLogData()
        log.logContent = msg
        log.gatewayName = self.gatewayName

        event = Event(EVENT_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)


class CoinbeneRestApi(RestClient):
    """REST API实现"""
    # ----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super().__init__()

        self.gateway = gateway  # type: CoinbeneGateway # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称

        self.apiKey = ''
        self.secretKey = ''

        self.orderID = 1000000
        self.loginTime = 0

        self.accountDict = gateway.accountDict
        self.orderDict = gateway.orderDict
        self.localOrderDict = gateway.localOrderDict

        self.accountid = ''  #
        self.cancelReqDict = {}
        self.orderBufDict = {}
        self.tickDict = {}
        self.dealDict = {}

        #self.queryAccountThread = None

    # ----------------------------------------------------------------------
    def sign(self, request):
        """Coinbene的签名方案"""
        if request.data:
            request.data = json.dumps(request.data)
            inputdata = request.data
            signature = self.generateSignature(inputdata, self.secretKey)
            request.headers = {
                'X-Coinbene-APIKEY': self.apiKey,
                'X-Coinbene-SIGNATURE': signature,
                'X-Coinbene-INPUT': inputdata,
                'Content-Type': 'application/json'
            }
        else:
            # 添加表头
            request.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",\
                "Content-Type":"application/json;charset=utf-8","Connection":"keep-alive"}
        return request

    def generateSignature(self, msg, apiSecret):
        """签名"""
        return base64.b64encode(hmac.new(bytes(apiSecret,'utf-8'), msg.encode(encoding='UTF8'), hashlib.sha384).digest())

    # ----------------------------------------------------------------------
    def connect(self, apiKey, secretKey, symbols, sessionCount=1):
        """连接服务器"""
        self.symbols = symbols
        self.apiKey = apiKey
        self.secretKey = secretKey
        self.loginTime = int(datetime.now().strftime('%y%m%d%H%M%S')) * self.orderID

        self.init(REST_HOST)
        self.start(sessionCount)
        #self.queryTicker()
        #self.reqThread = Thread(target=self.queryAccount)
        #self.reqThread.start()
        #self.queryAccount()
        self.initSubscribe()
        self.subscribe()

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):  # type: (VtOrderReq)->str
        try:
            self.gateway.localID += 1
            localID = str(self.gateway.localID)
            vtOrderID = '.'.join([self.gatewayName, localID])

            direction_ = directionMap[orderReq.direction]
            type_ = orderTypeMap[orderReq.orderType]
            data = {
                'Symbol': orderReq.symbol,  # 交易对
                'size': orderReq.volume,  # 交易数量
                'price': orderReq.price,
                'Side': direction_,  # 交易方向(0 买入 1 卖出)
                'type': type_,  # 订单类型 (0 市场价 1 限价)
                "Amount": float(orderReq.volume * orderReq.price)  # 订单总金额 - 市价必填
            }

            # 缓存委托
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = orderReq.symbol
            #order.exchange = 'Coinbene'
            order.vtSymbol = '.'.join([order.exchange, order.symbol])
            #order.orderID = localID
            order.vtOrderID = vtOrderID
            order.direction = orderReq.direction
            order.ordertType = orderReq.orderType
            order.price = orderReq.price
            order.volume = orderReq.volume
            #order.localID = localID
            # order.totalVolume = orderReq.volume * orderReq.price
            order.status = STATUS_UNKNOWN
            order.orderTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            self.orderBufDict[localID] = order

            self.addRequest('POST', '/api/v1/trade',
                            callback=self.onSendOrder,
                            data=data,
                            extra=localID)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelReq):
        try:
            data = {
                'Symbol': cancelReq.symbol,  # 交易对
                'OrderID': cancelReq.orderID,  # 订单Id
                'Side': directionMap[cancelReq.direction]  # 交易方向(0 买入 1 卖出)
            }
        except Exception as e:
            print(e)
        self.addRequest('POST', '/api/v1/cancel_order', callback=self.onCancelOrder, data=data, extra=cancelReq)

    # 取消全部订单
    def cancelAllOrders(self):
        data = 1
        self.addRequest('POST', '/api/v1/CancelAllOrders', callback=self.onCancelAllOrders, data=data)

    # ----------------------------------------------------------------------
    def queryAccount(self):
        """"""
        #while self._active:
        self.addRequest('POST', '/api/v1/getuserinfo', data="1",
                        callback=self.onQueryAccount)
            #time.sleep(5)  # 每隔5秒刷新账户信息

    def queryOrder(self):
        """"""
        for symbol in self.symbols:
            req = {
                'Symbol': symbol,
                "OrderID": 100
            }
            path = '/api/v1/getorderinfo'
            self.addRequest('POST', path, data=req,
                            callback=self.onQueryOrder)

    # 获取Coinbene历史订单信息，只返回最近7天的信息
    def queryHistoryOrder(self):
        """"""
        path = '/api/v1/gethistoryorder'
        for symbol in self.symbols:
            req = {
                'Symbol': symbol,
                "PageIndex": 1,  # 当前页数
                "PageSize": 200,  # 每页数据条数，最多不超过200
                "Status": orderStatusMap[STATUS_NOTTRADED]  # 未成交
            }
            self.addRequest('POST', path, data=req,
                            callback=self.onQueryHistoryOrder)

            req = {
                'Symbol': symbol,
                "PageIndex": 1,  # 当前页数
                "PageSize": 200,  # 每页数据条数，最多不超过200
                "Status": orderStatusMap[STATUS_PARTTRADED]  # 部分成交
            }
            self.addRequest('POST', path, data=req,
                            callback=self.onQueryHistoryOrder)

            req = {
                'Symbol': symbol,
                "PageIndex": 1,  # 当前页数
                "PageSize": 200,  # 每页数据条数，最多不超过200
                "Status": orderStatusMap[STATUS_ALLTRADED]  # 成交
            }
            self.addRequest('POST', path, data=req,
                            callback=self.onQueryHistoryOrder)
        self.gateway.writeLog('历史订单查询成功')

    def onQueryAccount(self, data, request):
        """"""
        if data['result'] == 1:
            for d in data['data']:
                currency = d['code']
                account = self.accountDict.get(currency, None)

                if not account:
                    account = VtAccountData()
                    account.gatewayName = self.gatewayName
                    account.accountID = d['code']
                    account.vtAccountID = '.'.join([account.gatewayName, account.accountID])

                    self.accountDict[currency] = account

                account.available = float(d['free'])
                account.margin = float(d['freezed'])

                account.balance = account.margin + account.available

            for account in self.accountDict.values():
                self.gateway.onAccount(account)

            #self.queryOrder()
            #self.queryHistoryOrder()
            #self.gateway.writeLog('资金信息查询成功')
        else:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
            return

    def onQueryOrder(self, data, request):
        if data['result'] == 1:
            try:
                for d in data['data']:
                    orderID = d['orderid']
                    strOrderID = str(orderID)

                    self.gateway.localID += 1
                    localID = str(self.gateway.localID)

                    #self.orderLocalDict[strOrderID] = localID
                    self.localOrderDict[localID] = strOrderID

                    order = VtOrderData()
                    order.gatewayName = self.gatewayName

                    order.orderID = localID
                    order.vtOrderID = '.'.join([order.gatewayName, order.orderID])

                    order.symbol = d['symbol']
                    order.exchange = EXCHANGE_Coinbene
                    order.vtSymbol = '.'.join([order.exchange, order.symbol])

                    order.price = float(d['price'])  # 委托价格
                    order.avgprice = float(d['avgprice'])  # 平均成交价
                    order.totalVolume = float(d['amount'])  # 委托数量
                    order.tradedVolume = float(d['executedamount'])  # 成交数量
                    order.status = orderStatusMapReverse[str(d['status'])]  # 订单状态
                    order.direction = directionMapReverse[d['side']]   # 交易方向   0 买入 1 卖出
                    order.orderType = orderTypeMapReverse[d['type']]  # 订单类型  0	市场价  1	 限价

                    dt = datetime.fromtimestamp(d['timestamp'])
                    order.orderTime = dt.strftime('%H:%M:%S')

                    self.orderDict[strOrderID] = order
                    self.gateway.onOrder(order)

            except Exception as e:
                print('Exception')
                print(e)
        else:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

    def onQueryHistoryOrder(self, data, request):
        if data['result'] == 1:
            self.gateway.processQueueOrder(data, historyFlag=1)
        else:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

    # ----------------------------------------------------------------------
    def onSendOrderFailed(self, data, request):
        """
        下单失败回调：服务器明确告知下单失败
        """
        order = request.extra
        order.status = STATUS_REJECTED
        self.gateway.onOrder(order)

    # ----------------------------------------------------------------------
    def onSendOrderError(self, exceptionType, exceptionValue, tb, request):
        """
        下单失败回调：连接错误
        """
        order = request.extra
        order.status = STATUS_REJECTED
        self.gateway.onOrder(order)

    # ----------------------------------------------------------------------
    def onSendOrder(self, data, request):
        localID = request.extra
        order = self.orderBufDict[localID]

        if data['result'] != 1:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

            order.status = STATUS_REJECTED
            self.gateway.onOrder(order)
        else:
            order.status = STATUS_ORDERED  # 已报
            strOrderID = data['data']['orderid']

            self.localOrderDict[localID] = strOrderID
            order.orderID = strOrderID  # 服务器返回orderid写入order
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])  # 本地队列索引
            self.orderDict[strOrderID] = order
            self.gateway.onOrder(order)

            #req = self.cancelReqDict.get(localID, None)
            #if req:
            #    self.cancelOrder(req)

    # ----------------------------------------------------------------------
    def onCancelOrder(self, data, request):
        if data['result'] != 1:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            order = request.extra
            order.status = STATUS_CANCELLED # 订单状态
            self.gateway.onOrder(order)

    def onCancelAllOrders(self, data, request):
        if data['result'] != 1:
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            return


    def initSubscribe(self):
        # 初始化
        for symbol in self.symbols:
            # l.append('ticker.' + symbol)
            # l.append('depth.L20.' + symbol)
            tick = VtTickData()
            tick.gatewayName = self.gatewayName
            tick.symbol = symbol
            tick.exchange = EXCHANGE_COINBENE
            tick.vtSymbol = '.'.join([tick.exchange, tick.symbol])
            self.tickDict[symbol] = tick
            self.dealDict[symbol] = tick

    def subscribe(self):
        depth = 5
        dealSize = 20
        for symbol in self.symbols:
            # 获取市场深度
            path = "/v1/market/orderbook?symbol=" + symbol + "&depth=" + str(depth)
            self.addRequest('GET', path,
                            callback=self.onDepth,
                            onFailed=self.onFailed,
                            onError=self.onError)

            path = "/v1/market/ticker?symbol=" + symbol
            self.addRequest('GET', path,
                            callback=self.onTick,
                            onFailed=self.onFailed,
                            onError=self.onError)

            """
            path = "/v1/market/trades?symbol=" + symbol + "&size=" + str(dealSize)
            self.addRequest('GET', path,
                            callback=self.onDeal,
                            onFailed=self.onFailed,
                            onError=self.onError)
            """

    # ----------------------------------------------------------------------
    def onTick(self, data, request):
        if data['status'] != 'ok':
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['description'])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            data = data['ticker'][0]

            symbol = data['symbol']
            tick = self.tickDict[symbol]
            tick.lastPrice = float(data['last'])
            tick.highPrice = float(data['24hrHigh'])
            tick.lowPrice = float(data['24hrLow'])
            tick.volume = float(data['24hrVol'])

            self.gateway.onTick(tick)

    def onDeals(self, data, request):
        return
        if data['status'] != 'ok':
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            data = data['ticker']

            symbol = data['symbol']
            deal = self.dealDict[symbol]
            deal.lastPrice = float(data['price'])
            deal.volume = float(data['amount'])
            deal.type = dealStatusMapReverse[data['type']]
            try:
                deal.datetime = datetime.fromtimestamp(data['timestamp'])
                deal.time = deal.datetime.strftime('%H:%M:%S')
                self.gateway.onDeal(deal)
            except Exception as e:
                print(e)

    # ----------------------------------------------------------------------
    def onDepth(self, data, request):
        if data['status'] != 'ok':
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            try:
                symbol = data['symbol']
                #print('symbol is %s'%(symbol))
                tick = self.tickDict[symbol]

                bids = data['orderbook']['bids']
                asks = data['orderbook']['asks']

                depth = 20
                # 买单
                try:
                    for index in range(depth):
                        para = "bidPrice" + str(index + 1)
                        if index >= len(bids):
                            setattr(tick, para, 0)
                        else:
                            setattr(tick, para, bids[index]['price'])

                        para = "bidVolume" + str(index + 1)
                        if index >= len(bids):
                            setattr(tick, para, 0)
                        else:
                            setattr(tick, para, float(bids[index]['quantity']))  # float can sum
                except Exception as e:
                    print(e)

                # 卖单
                try:
                    for index in range(depth):
                        para = "askPrice" + str(index + 1)
                        if index >= len(asks):
                            setattr(tick, para, 0)
                        else:
                            setattr(tick, para, asks[index]['price'])

                        para = "askVolume" + str(index + 1)
                        if index >= len(asks):
                            setattr(tick, para, 0)
                        else:
                            setattr(tick, para, float(asks[index]['quantity']))
                except Exception as e:
                    print(e)

                tick.datetime = datetime.fromtimestamp(data['timestamp']/1000)
                tick.date = tick.datetime.strftime('%Y%m%d')
                tick.time = tick.datetime.strftime('%H:%M:%S')

                self.gateway.onTick(copy(tick))
            except Exception as e:
                print(e)

    # ----------------------------------------------------------------------
    def onFailed(self, httpStatusCode, request):  # type:(int, Request)->None
        """
        请求失败处理函数（HttpStatusCode!=2xx）.
        默认行为是打印到stderr
        """
        e = VtErrorData()
        e.gatewayName = self.gatewayName
        e.errorID = httpStatusCode
        e.errorMsg = request.response.text
        self.gateway.onError(e)
        print(request.response.text)

    # ----------------------------------------------------------------------
    def onError(self, exceptionType, exceptionValue, tb, request):
        """
        Python内部错误处理：默认行为是仍给excepthook
        """
        e = VtErrorData()
        e.gatewayName = self.gatewayName
        e.errorID = exceptionType
        e.errorMsg = exceptionValue
        self.gateway.onError(e)

        sys.stderr.write(self.exceptionDetail(exceptionType, exceptionValue, tb, request))

