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

# 委托状态类型映射
orderStatusMap = {}
#orderStatusMap[STATUS_CANCELLED] = -2
#orderStatusMap[STATUS_NOTVALID] = -1
orderStatusMap[STATUS_NOTTRADED] = 'unfilled'
orderStatusMap[STATUS_PARTTRADED] = 'partialFilled'
#orderStatusMap[STATUS_ALLTRADED] = 2
#orderStatusMap[STATUS_ORDERED] = 3

# 方向和订单类型映射
directionMap = {}
directionMap[(DIRECTION_BUY)] = 'buy-limit'
directionMap[(DIRECTION_SELL)] = 'sell-limit'

orderStatusMapReverse = {v: k for k, v in orderStatusMap.items()}
directionMapReverse = {v: k for k, v in directionMap.items()}

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

    def processQueueOrder(self, data):
        if data['orders'] is None:
            return
        for d in data['orders']['result']:
            # self.gateway.localID += 1
            # localID = str(self.gateway.localID)

            order = VtOrderData()
            order.gatewayName = self.gatewayName

            order.symbol = d['symbol']
            order.exchange = EXCHANGE_COINBENE
            order.vtSymbol = '.'.join([order.exchange, order.symbol])

            order.orderID = d['orderid']
            # order.vtOrderID = '.'.join([self.gatewayName, localID])
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])

            order.price = float(d['price'])  # 委托价格
            #order.avgprice = float(d['avgprice'])  # 平均成交价
            order.volume = float(d['orderquantity'])  # 委托数量
            order.tradedVolume = float(d['filledquantity'])  # 成交数量
            order.status = orderStatusMapReverse[d['orderstatus']]  # 订单状态
            order.direction = directionMapReverse[d['type']]  # 交易方向   0 买入 1 卖出
            #order.orderType = orderTypeMapReverse[d['type']]  # 订单类型  0	市场价  1	 限价

            dt = datetime.fromtimestamp(d['createtime']/1000)
            order.orderTime = dt.strftime('%Y-%m-%d %H:%M:%S')

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
        self.symbols = {}

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
            request.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",\
                "Content-Type":"application/json;charset=utf-8","Connection":"keep-alive"}
        else:
            # 添加表头
            request.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",\
                "Content-Type":"application/json;charset=utf-8","Connection":"keep-alive"}
        return request

    def generateSignature(self, **kwargs):
        """签名"""
        sign_list = []
        for key, value in kwargs.items():
            sign_list.append("{}={}".format(key, value))
        sign_list.sort()
        sign_str = "&".join(sign_list)
        mysecret = sign_str.upper().encode()
        m = hashlib.md5()
        m.update(mysecret)
        return m.hexdigest()

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
        self.initSubscribe()
        self.subscribe()
        self.queryAccount()
        self.queryOpenOrders()

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):  # type: (VtOrderReq)->str
        try:
            self.gateway.localID += 1
            localID = str(self.gateway.localID)
            vtOrderID = '.'.join([self.gatewayName, localID])

            direction_ = directionMap[orderReq.direction]
            timestamp = int(time.time())
            dic = {
                'apiid': self.apiKey,
                'price': orderReq.price,
                'quantity': orderReq.volume,  # 交易数量
                'symbol': orderReq.symbol,  # 交易对
                'type': direction_,  # buy-limit, sell-limit	限价买入 / 限价卖出
                'secret': self.secretKey,
                'timestamp': timestamp
            }

            # 缓存委托
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = orderReq.symbol
            order.exchange = EXCHANGE_COINBENE
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

            mysign = self.generateSignature(**dic)
            del dic['secret']
            dic['sign'] = mysign
            self.addRequest('POST', '/v1/trade/order/place',
                            callback=self.onSendOrder,
                            data=dic,
                            extra=localID)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelReq):
        timestamp = int(time.time())
        try:
            dic = {
                'apiid': self.apiKey,
                'orderid': cancelReq.orderID,
                'secret': self.secretKey,
                'timestamp': timestamp
            }

            mysign = self.generateSignature(**dic)
            del dic['secret']
            dic['sign'] = mysign
            self.addRequest('POST', '/v1/trade/order/cancel', callback=self.onCancelOrder, data=dic, extra=cancelReq)
        except Exception as e:
            print(e)

    # 取消全部订单
    #def cancelAllOrders(self):
    #    data = 1
    #    self.addRequest('POST', '/api/v1/CancelAllOrders', callback=self.onCancelAllOrders, data=data)

    # ----------------------------------------------------------------------
    def queryAccount(self):
        """"""
        #while self._active:
        timestamp = int(time.time())
        dic = {
            'account': 'exchange',
            'apiid': self.apiKey,
            'secret':self.secretKey,
            'timestamp':timestamp
        }
        try:
            mysign = self.generateSignature(**dic)
            del dic['secret']
            dic['sign'] = mysign
            self.addRequest('POST', '/v1/trade/balance', data=dic,
                            callback=self.onQueryAccount)
        except Exception as e:
            print(e)
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

    # 获取Coinbene当前委托
    def queryOpenOrders(self):
        for symbol in self.symbols:
            timestamp = int(time.time())
            dic = {
                'apiid': self.apiKey,
                'secret':self.secretKey,
                'timestamp':timestamp,
                'symbol': symbol,
            }
            try:
                mysign = self.generateSignature(**dic)
                del dic['secret']
                dic['sign'] = mysign
                self.addRequest('POST', '/v1/trade/order/open-orders', data=dic,
                                callback=self.onQueryOpenOrders)
            except Exception as e:
                print(e)
        self.gateway.writeLog('当前订单查询成功')

    def onQueryAccount(self, data, request):
        """"""
        if data['status'] == 'ok':
            for d in data['balance']:
                currency = d['asset']
                account = self.accountDict.get(currency, None)

                if not account:
                    account = VtAccountData()
                    account.gatewayName = self.gatewayName
                    account.accountID = currency
                    account.vtAccountID = '.'.join([account.gatewayName, account.accountID])

                    self.accountDict[currency] = account

                account.available = float(d['available'])
                account.margin = float(d['reserved'])

                account.balance = account.margin + account.available

            for account in self.accountDict.values():
                self.gateway.onAccount(account)

            #self.queryOrder()
            #self.queryHistoryOrder()
            #self.gateway.writeLog('资金信息查询成功')
        else:
            msg = '错误信息：%s' % (data['description'])
            self.gateway.writeLog(msg)
            return

    def onQueryOrder(self, data, request):
        if data['result'] == 'ok':
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
            msg = '错误信息：%s' % (data['description'])
            self.gateway.writeLog(msg)

    def onQueryOpenOrders(self, data, request):
        if data['status'] == 'ok':
            self.gateway.processQueueOrder(data)
        else:
            msg = '错误信息：%s' % (data['description'])
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

        if data['status'] != 'ok':
            msg = '错误信息：%s' % (data['description'])
            self.gateway.writeLog(msg)

            order.status = STATUS_REJECTED
            self.gateway.onOrder(order)
        else:
            order.status = STATUS_ORDERED  # 已报
            strOrderID = data['orderid']

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
        if data['status'] != 'ok':
            msg = '错误信息：%s' % (data['description'])
            self.gateway.writeLog(msg)
        else:
            order = request.extra
            order.status = STATUS_CANCELLED # 订单状态
            self.gateway.onOrder(order)

    def onCancelAllOrders(self, data, request):
        if data['result'] != 'ok':
            msg = '错误信息：%s' % (data['description'])
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
        #dealSize = 20
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
            msg = '错误信息：%s' % (data['description'])
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
            msg = '错误信息：%s' % (data['description'])
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

