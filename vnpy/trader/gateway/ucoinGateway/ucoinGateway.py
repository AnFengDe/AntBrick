# encoding: UTF-8

'''
UCOIN交易接口
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
from vnpy.api.websocket import WebsocketClient
from vnpy.api.ucoin import UcoinWebsocketApi
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

from threading import Thread

REST_HOST = 'http://testapi.ucoin.pw'  # 测试网
WEBSOCKET_HOST = 'http://testapi.ucoin.pw'
EXCHANGE_UCOIN = "UCOIN"

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

#错误码对应表
errMsgMap = {}
errMsgMap[10001] = '验证失败'
errMsgMap[10002] = '系统错误'
errMsgMap[10003] = '该连接已经请求了其他用户的实时交易数据'


def getErrMsg(errcode):
    return errMsgMap[errcode]
    msg = u'错误代码：%s, 错误信息：%s' % (data['code'], errMsg)
    self.gateway.writeLog(msg)


class UcoinGateway(VtGateway):
    """ucoin接口"""
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

        self.restApi = UcoinRestApi(self)
        #self.wsApi = WebsocketApi(self)

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
            log.logContent = u'读取连接配置出错，请检查'
            self.onLog(log)
            return

        # 解析json文件
        setting = json.load(f)
        f.close()

        try:
            apiKey = str(setting['apiKey'])
            account = str(setting['account'])
            password = str(setting['password'])
            symbols = setting['symbols']
            coins = setting['coins']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return

        # 创建行情和交易接口对象
        self.restApi.connect(apiKey, account, password, symbols, coins)
        #self.wsApi.connect(apiKey, account, password, symbols)

        # 初始化并启动查询
        #self.initQuery()

    def subscribe(self, subscribeReq):
        """订阅行情"""
        self.wsApi.subscribe(subscribeReq)

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        self.restApi.sendOrder(orderReq)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.restApi.cancelOrder(cancelOrderReq)

    # ----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.restApi.stop()
        #self.wsApi.close()

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
        #self.restApi.queryPosition()

    def processQueueOrder(self, data, symbol):
        for d in data['data']:
            # self.gateway.localID += 1
            # localID = str(self.gateway.localID)

            order = VtOrderData()
            order.gatewayName = self.gatewayName

            order.symbol = symbol
            order.exchange = EXCHANGE_UCOIN
            order.vtSymbol = '.'.join([order.symbol, order.exchange])

            order.orderID = d['tid']
            # order.vtOrderID = '.'.join([self.gatewayName, localID])
            order.vtOrderID = self.gatewayName + '.' + str(order.orderID)

            #order.price = float(d['price'])  # 委托价格
            order.avgprice = float(d['price'])  # 平均成交价
            #order.volume = float(d['amount']) + float(d['executedamount'])  # 委托数量
            order.tradedVolume = float(d['number'])  # 成交数量
            #order.status = orderStatusMapReverse[d['status']]  # 订单状态
            order.direction = directionMapReverse[d['type']]  # 交易方向   0 买入 1 卖出
            #order.orderType = orderTypeMapReverse[d['type']]  # 订单类型  0	市场价  1	 限价

            order.orderTime = d['created_at']

            self.onTrade(order)

    def writeLog(self, msg):
        """"""
        log = VtLogData()
        log.logContent = msg
        log.gatewayName = self.gatewayName

        event = Event(EVENT_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)


class UcoinRestApi(RestClient):
    """REST API实现"""
    # ----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super().__init__()

        self.gateway = gateway  # type: UcoinGateway # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称

        self.apiKey = ''
        self.access_token = ''

        self.orderID = 1000000
        self.loginTime = 0

        self.accountDict = gateway.accountDict
        self.orderDict = gateway.orderDict
        self.localOrderDict = gateway.localOrderDict

        self.accountid = ''  #
        self.cancelReqDict = {}
        self.orderBufDict = {}
        self.tickDict = {}

        #self.queryAccountThread = None

    def login(self):
        try:
            currentTime = str(int(time.time()))
            signature = self.generateSignature(currentTime, self.apiKey)
            data = {
                'cur_time': currentTime,
                'sign': signature,
                'login_field': self.account,
                'password': self.password,
                'key': self.apiKey
            }
            self.addRequest('POST', '/api/open/getToken',
                            callback=self.onLogin,
                            data=data)
        except Exception as e:
            print(e)

    def onLogin(self, data, request):
        if data['code'] == '0':
            self.access_token = data['data']['access_token']
        else:
            try:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], errMsgMap[int(data['code'])])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

    def sign(self, request):
        if request.data:
            request.data = json.dumps(request.data)

        #inputdata = request.data
        #signature = self.generateSignature(inputdata, self.apiKey)

        # 添加表头
        authString = 'Bearer '+ self.access_token
        if self.access_token is not '':
            request.headers = {
                'Authorization': authString,
                'Content-Type': 'application/json'
            }
        else:
            request.headers = {
                'Content-Type': 'application/json'
            }
        #print(request.headers)
        return request

    def generateSignature(self, curTime, apiSecret):
        # api_key 拼接 当前时间戳 进行md5加密
        # sign = md5(api_key + cur_time)
        convertStr = apiSecret + curTime
        return hashlib.md5(convertStr.encode()).hexdigest()

    # ----------------------------------------------------------------------
    def connect(self, apiKey, account, password, symbols, coins, sessionCount=1):
        """连接服务器"""
        self.apiKey = apiKey
        self.account = account
        self.password = password
        self.symbols = symbols
        self.coins = coins

        #self.loginTime = int(datetime.now().strftime('%y%m%d%H%M%S')) * self.orderID
        self.loginTime = datetime.now()

        self.init(REST_HOST)
        self.start(sessionCount)
        self.login()
        #self.reqThread = Thread(target=self.queryAccount)
        #self.reqThread.start()
        self.queryAccount()
        self.queryHistoryOrder()
        self.subscribeMarketData()

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):  # type: (VtOrderReq)->str
        try:
            self.gateway.localID += 1
            localID = str(self.gateway.localID)
            vtOrderID = '.'.join([self.gatewayName, localID])

            direction_ = directionMap[orderReq.direction]

            currentTime = str(int(time.time()))
            signature = self.generateSignature(currentTime, self.apiKey)
            #type_ = orderTypeMap[orderReq.orderType]
            data = {
                'cur_time': currentTime,
                'sign': signature,
                'price': str(orderReq.price),
                'number': str(orderReq.volume),  # 交易数量
                'type': str(direction_)  # 交易方向(0 买入 1 卖出)
                #'type': type_,  # 订单类型 (0 市场价 1 限价)
            }

            # 缓存委托
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = orderReq.symbol
            order.vtSymbol = '.'.join([order.symbol, order.exchange])
            #order.orderID = localID
            order.vtOrderID = vtOrderID
            order.direction = orderReq.direction
            #order.ordertType = orderReq.orderType
            order.price = orderReq.price
            order.volume = orderReq.volume
            #order.localID = localID
            # order.totalVolume = orderReq.volume * orderReq.price
            order.status = STATUS_UNKNOWN
            order.orderTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            self.orderBufDict[localID] = order

            url= ('/api/open/trade/order/' + order.symbol).lower()
            self.addRequest('POST', url,
                            callback=self.onSendOrder,
                            data=data,
                            #nFailed=self.onSendOrderFailed,
                            extra=localID)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelReq):
        try:
            currentTime = str(int(time.time()))
            signature = self.generateSignature(currentTime, self.apiKey)
            data = {
                'cur_time': currentTime,
                'sign': signature,
                'order_id': cancelReq.orderID,  # 订单Id
                'type': directionMap[cancelReq.direction]  # 交易方向(0 买入 1 卖出)
            }
        except Exception as e:
            print(e)
        self.addRequest('POST', '/api/open/trade/cancelOrder', callback=self.onCancelOrder, data=data, extra=cancelReq)

    def subscribeMarketData(self):
        # 订阅行情
        for symbol in self.symbols:
            tick = VtTickData()
            tick.gatewayName = self.gatewayName
            tick.symbol = symbol
            tick.exchange = "UCOIN"
            tick.vtSymbol = tick.exchange + '.' + tick.symbol
            self.tickDict[symbol] = tick
        self.queryTick()
        self.queryDepth()

    # 获取UCOIN最新币币行情数据
    def queryTick(self):
        """"""
        try:
            for symbol in self.symbols:
                path = '/api/open/ticker/' + symbol
                self.addRequest('GET', path = path,
                    callback=self.onTick)
        except Exception as e:
            print(e)

    def queryDepth(self):
        for symbol in self.symbols:
            path = '/api/open/depth/' + symbol
            self.addRequest('GET', path = path, data={"size": "40"},
                callback=self.onDepth, extra=symbol)

    def onTick(self, data, request):
        try:
            if data['code'] == '0':
                data = data['data']
                symbol = data['name']
                tick = self.tickDict[symbol]
                tick.lastPrice = float(data['price'])
                tick.highPrice = float(data['high'])
                tick.lowPrice = float(data['low'])
                tick.volume = float(data['number'])

                self.gateway.onTick(tick)
        except Exception as e:
            print(e)

    def onDepth(self, data, request):
        try:
            if data['code'] == '0':
                data = data['data']
                symbol = request.extra
                tick = self.tickDict[symbol]

                bids = data['bids']
                asks = data['asks']

                depth = 20
                try:
                    for index in range(depth):
                        if index == len(bids):
                            break
                        para = "bidPrice" + str(index+1)
                        setattr(tick, para, bids[index]['price'])

                        para = "bidVolume" + str(index+1)
                        setattr(tick, para, float(bids[index]['undeal']))
                except Exception as e:
                    print(e)

                try:
                    for index in range(depth):
                        if index == len(asks):
                            break
                        para = "askPrice" + str(index+1)
                        setattr(tick, para, asks[index]['price'])

                        para = "askVolume" + str(index+1)
                        setattr(tick, para, float(asks[index]['undeal']))
                except Exception as e:
                    print(e)

                #tick.datetime = datetime.fromtimestamp(d['timestamp'])
                #tick.date = tick.datetime.strftime('%Y%m%d')
                #tick.time = tick.datetime.strftime('%H:%M:%S')

                self.gateway.onTick(copy(tick))
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def queryAccount(self):
        for coin in self.coins:
            url = '/api/open/account/getBalance/' + coin
            self.addRequest('GET', url, callback=self.onQueryAccount)

    # 测试用
    #def getBalance(self):
    #    self.addRequest('GET', '/api/open/account/getBalance/BSTC', callback=self.onQueryAccount)
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

    # 获取Ucoin历史订单信息
    def queryHistoryOrder(self):
        """"""
        for symbol in self.symbols:
            path = '/api/open/trades/' + symbol
            self.addRequest('GET', path,
                            callback=self.onQueryHistoryOrder,extra=symbol)

        self.gateway.writeLog(u'历史订单查询成功')

    def onQueryAccount(self, data, request):
        if data['code'] == '0':
            d = data['data']
            currency = d['coin_name']
            account = self.accountDict.get(currency, None)

            if not account:
                account = VtAccountData()
                account.gatewayName = self.gatewayName
                account.accountID = d['coin_name']
                account.vtAccountID = account.gatewayName + '.' + account.accountID

                self.accountDict[currency] = account

            account.available = float(d['available'])
            account.margin = float(d['disabled'])
            account.balance = account.margin + account.available

            self.gateway.onAccount(account)
        else:
            try:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

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
                    order.exchange = EXCHANGE_UCOIN
                    order.vtSymbol = '.'.join([order.symbol, order.exchange])

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
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

    def onQueryHistoryOrder(self, data, request):
        #print(data)
        if data['code'] == '0':
            self.gateway.processQueueOrder(data, symbol=request.extra)
        else:
            try:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

    # ----------------------------------------------------------------------
    def onSendOrder(self, data, request):
        localID = request.extra
        order = self.orderBufDict[localID]

        if data['code'] != '0':
            try:
                msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)

            order.status = STATUS_REJECTED
            self.gateway.onOrder(order)
        else:
            order.status = STATUS_ORDERED  # 已报
            strOrderID = str(data['data']['order_id'])

            self.localOrderDict[localID] = strOrderID
            order.orderID = strOrderID  # 服务器返回orderid写入order
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])  # 本地队列索引
            self.orderDict[strOrderID] = order
            self.gateway.onOrder(order)

            #req = self.cancelReqDict.get(localID, None)
            #if req:
            #    self.cancelOrder(req)

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
    def onCancelOrder(self, data, request):
        if data['code'] != '0':
            try:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            except Exception as e:
                msg = u'错误代码：%s, 错误信息：%s' % (data['code'], '错误信息未知')
            self.gateway.writeLog(msg)
        else:
            order = request.extra
            order.status = STATUS_CANCELLED # 订单状态
            self.gateway.onOrder(order)

    # ----------------------------------------------------------------------
    def onFailed(self, httpStatusCode, request):  # type:(int, Request)->None
        """
        请求失败处理函数（HttpStatusCode!=2xx）.
        默认行为是打印到stderr
        """
        e = VtErrorData()
        e.gatewayName = self.gatewayName
        e.errorID = httpStatusCode
        print(json.loads(request.response.text)['code'])
        print(json.loads(request.response.text)['msg'])
        e.errorMsg = json.loads(request.response.text)['code'] + ',' + json.loads(request.response.text)['msg']
        self.gateway.onError(e)

    # ----------------------------------------------------------------------
    def onError(self, exceptionType, exceptionValue, tb, request):
        #Python内部错误处理：默认行为是仍给excepthook
        e = VtErrorData()
        e.gatewayName = self.gatewayName
        e.errorID = exceptionType
        e.errorMsg = exceptionValue
        self.gateway.onError(e)

        sys.stderr.write(self.exceptionDetail(exceptionType, exceptionValue, tb, request))

class WebsocketApi(UcoinWebsocketApi):
    def __init__(self, gateway):
        #Constructor
        super().__init__()

        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.apiKey = ''
        self.account = ''
        self.password = ''
        self.symbols = ''

        self.accountDict = gateway.accountDict
        self.orderDict = gateway.orderDict
        self.localOrderDict = gateway.localOrderDict

        self.tradeID = 0
        self.callbackDict = {}
        self.channelSymbolDict = {}
        self.tickDict = {}
        self.dealDict = {}

    # ----------------------------------------------------------------------
    def unpackData(self, data):
        #重载
        return json.loads(zlib.decompress(data, -zlib.MAX_WBITS))

    # ----------------------------------------------------------------------
    def connect(self, apiKey, account, password, symbols):
        self.apiKey = apiKey
        self.account = account
        self.password = password
        self.symbols = symbols

        self.start()
        #for symbol in symbols:
        #    self.subscribeMarketData(symbol)

    def subscribeMarketData(self, symbol):
        # 订阅行情
        for symbol in self.symbols:
            tick = VtTickData()
            tick.gatewayName = self.gatewayName
            tick.symbol = symbol
            tick.exchange = "UCOIN"
            tick.vtSymbol = '.'.join([tick.symbol, tick.exchange])
            self.tickDict[symbol] = tick
        #

    def onConnect(self):
        #连接回调
        self.gateway.writeLog(u'Websocket API连接成功')
        self.login()

    def onData(self, data):
        #数据回调
        if 'Event' in data:
            if data['Event'] == "login":
                if data["Result"]:
                    # 连接成功,开始订阅
                    # return
                    self.subscribe()
                else:
                    self.gateway.writeLog("login error ", data["Errorcode"])
        elif 'channel' in data:
            # print(data)
            if 'depth' in data['channel']:
                self.onDepth(data)
            elif 'ticker' in data['channel']:
                self.onTick(data)
            elif 'deals' in data['channel']:
                self.onDeals(data)
            elif 'balance' in data['channel']:
                self.onBalance(data)
            elif 'order' in data['channel']:
                self.onOrder(data)

    def onOrder(self, data):
        self.gateway.processQueueOrder(data, historyFlag=0)

    # ----------------------------------------------------------------------
    def onDisconnected(self):
        #连接回调
        self.gateway.writeLog(u'Websocket API连接断开')

    # ----------------------------------------------------------------------
    def onPacket(self, packet):
        # 数据回调
        d = packet[0]

        channel = d['channel']
        callback = self.callbackDict.get(channel, None)
        if callback:
            callback(d)

    @staticmethod
    def sign(apiKey):
        # 拼接apikey = {你的apikey} & secret_key = {你的secretkey} 进行MD5，结果大写
        convertStr = "apikey=" + apiKey + "&secret_key=" + secretkey
        return hashlib.md5(convertStr.encode()).hexdigest().upper()

    def login(self):
        try:
            signature = self.sign(self.apiKey)
            req = {
                "event": "login",
                "parameters": {
                    "ApiKey": self.apiKey,
                    "Sign": signature
                }
            }
            self.sendReq(req)
        except Exception as e:
            print(e)

    def subscribe(self):
        # 初始化
        for symbol in self.symbols:
            #l.append('ticker.' + symbol)
            #l.append('depth.L20.' + symbol)
            tick = VtTickData()
            tick.gatewayName = self.gatewayName
            tick.symbol = symbol
            tick.exchange = EXCHANGE_UCOIN
            tick.vtSymbol = '.'.join([tick.symbol, tick.exchange])
            self.tickDict[symbol] = tick
            self.dealDict[symbol] = tick

        for symbol in self.symbols:
            # 订阅行情深度,支持5，10，20档
            channel = "idcm_sub_spot_" + symbol + "_depth_20"
            req = {
                'event': 'addChannel',
                'channel': channel
            }
            self.sendReq(req)

            # 订阅行情数据
            channel = "idcm_sub_spot_" + symbol + "_ticker"
            req = {
                'event': 'addChannel',
                'channel': channel
            }
            self.sendReq(req)

            # 订阅成交记录
            channel = "idcm_sub_spot_" + symbol + "_deals"
            req = {
                'event': 'addChannel',
                'channel': channel
            }
            self.sendReq(req)

    # ----------------------------------------------------------------------
    def onTick(self, d):
        data = d['data']

        symbol = d['channel'].split('_')[3]
        tick = self.tickDict[symbol]
        tick.lastPrice = float(data['last'])
        tick.highPrice = float(data['high'])
        tick.lowPrice = float(data['low'])
        tick.volume = float(data['vol'])

        self.gateway.onTick(tick)

    def onDeals(self, d):
        data = d['data'][0]

        symbol = d['channel'].split('_')[3]
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
    def onDepth(self, d):
        try:
            symbol = d['channel'].split('_')[3]
            tick = self.tickDict[symbol]

            bids = d['data']['bids']
            asks = d['data']['asks']

            depth = 20
            try:
                for index in range(depth):
                    if index == len(bids):
                        break
                    para = "bidPrice" + str(index+1)
                    setattr(tick, para, bids[index]['Price'])

                    para = "bidVolume" + str(index+1)
                    setattr(tick, para, bids[index]['Amount'])
            except Exception as e:
                print(e)

            try:
                for index in range(depth):
                    if index == len(asks):
                        break
                    para = "askPrice" + str(index+1)
                    setattr(tick, para, asks[index]['Price'])

                    para = "askVolume" + str(index+1)
                    setattr(tick, para, asks[index]['Amount'])
            except Exception as e:
                print(e)

            tick.datetime = datetime.fromtimestamp(d['timestamp'])
            tick.date = tick.datetime.strftime('%Y%m%d')
            tick.time = tick.datetime.strftime('%H:%M:%S')

            self.gateway.onTick(copy(tick))
        except Exception as e:
            print(e)

    def onBalance(self, d):
        currency = d['channel'].split('_')[3]  # format:idcm_sub_spot_ETH_balance
        account = self.accountDict.get(currency, None)

        data = d['data']
        account.available = float(data['free'])
        account.margin = float(data['freezed'])

        account.balance = account.margin + account.available

        self.gateway.onAccount(account)
