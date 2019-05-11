# encoding: UTF-8

'''
Coinw交易接口
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

REST_HOST = 'https://api.coinw.ai'
EXCHANGE_Coinw = "Coinw"

# 委托状态类型映射
orderStatusMap = {}
#orderStatusMap[STATUS_NOTVALID] = -1
orderStatusMap[STATUS_NOTTRADED] = '1'
orderStatusMap[STATUS_PARTTRADED] = '2'
orderStatusMap[STATUS_ALLTRADED] = '3'
orderStatusMap[STATUS_CANCELLED] = '4'
#orderStatusMap[STATUS_ALLTRADED] = 2
#orderStatusMap[STATUS_ORDERED] = 3

# 方向和订单类型映射
directionMap = {}
directionMap[(DIRECTION_BUY)] = 0
directionMap[(DIRECTION_SELL)] = 1

orderStatusMapReverse = {v: k for k, v in orderStatusMap.items()}
directionMapReverse = {v: k for k, v in directionMap.items()}

class CoinwGateway(VtGateway):
    """Coinw接口"""

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

        self.restApi = CoinwRestApi(self)

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
            coins = setting['coins']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = '连接配置缺少字段，请检查'
            self.onLog(log)
            return

        # 创建行情和交易接口对象
        self.restApi.connect(apiKey, secretKey, symbols, coins)

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
        self.restApi.cancelAllOrders()

    def queryOrder(self, orderid):
        #查询委托
        self.restApi.queryOrder(orderid)

    def queryOpenOrders(self):
        #查询委托
        self.restApi.queryOpenOrders()

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
        if data['data'] is None:
            return
        for d in data['data']:
            order = VtOrderData()
            order.orderID = str(d['id'])
            order.gatewayName = self.gatewayName
            order.vtOrderID = '.'.join([order.gatewayName, order.orderID])
            order.exchange = EXCHANGE_Coinw
            order.symbol=data['symbol']
            order.vtSymbol = '.'.join([order.exchange, order.symbol])

            order.price = float(d['price'])  # 委托价格
            order.avgprice = float(d['price'])  # 平均成交价
            order.totalVolume = float(d['count'])  # 委托数量
            order.tradedVolume = float(d['success_count'])  # 成交数量
            order.status = orderStatusMapReverse[str(d['status'])]  # 订单状态
            order.direction = directionMapReverse[d['type']]  # 交易方向   0 买入 1 卖出

            dt = datetime.fromtimestamp(d['timestamp'])
            order.orderTime = dt.strftime('%H:%M:%S')

            self.orderDict[strOrderID] = order
            self.onOrder(order)

    def writeLog(self, msg):
        """"""
        log = VtLogData()
        log.logContent = msg
        log.gatewayName = self.gatewayName

        event = Event(EVENT_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)


class CoinwRestApi(RestClient):
    """REST API实现"""
    # ----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super().__init__()

        self.gateway = gateway  # type: CoinwGateway # gateway对象
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
        """Coinw的签名方案"""
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
        sign_str += ("&secret_key=" + self.secretKey)
        #mysecret = sign_str.upper().encode()
        mysecret = sign_str.encode()
        m = hashlib.md5()
        m.update(mysecret)
        return m.hexdigest().upper()

    # ----------------------------------------------------------------------
    def connect(self, apiKey, secretKey, symbols, coins, sessionCount=1):
        """连接服务器"""
        self.symbols = symbols
        self.coins = coins
        self.apiKey = apiKey
        self.secretKey = secretKey
        self.loginTime = int(datetime.now().strftime('%y%m%d%H%M%S')) * self.orderID

        self.init(REST_HOST)
        self.start(sessionCount)
        #self.queryTicker()
        #self.reqThread = Thread(target=self.queryAccount)
        #self.reqThread.start()
        self.initSubscribe()
        self.getSymbol()
        time.sleep(3)  # 等待getSymbol完成
        for i in range(1, 5):
            if hasattr(self,'symbolsList'):
                self.subscribe(None)
                time.sleep(1)
                self.queryAccount()
                break
            else:
                if i < 5:
                    time.sleep(2)
                else:
                    self.gateway.writeLog('getSymbol失败,请检查网络')
                    self.stop()

        #self.queryOpenOrders()

    # ----------------------------------------------------------------------
    def sendOrder(self, orderReq):  # type: (VtOrderReq)->str
        try:
            self.gateway.localID += 1
            localID = str(self.gateway.localID)
            vtOrderID = '.'.join([self.gatewayName, localID])

            direction_ = directionMap[orderReq.direction]
            dic = {
                'api_key': self.apiKey,
                'price': orderReq.price,
                'amount': orderReq.volume,  # 交易数量
                'symbol': self.symbolsKeys[orderReq.symbol],  # 交易对
                'type': direction_  # buy-limit, sell-limit	限价买入 / 限价卖出
                #'secret_key': self.secretKey
            }
            path = "/appApi.html?action=trade&symbol=" + self.symbolsKeys[orderReq.symbol]
            path += ("&type=" + str(direction_))
            path += ("&amount=" + str(orderReq.volume))
            path += ("&price=" + str(orderReq.price))

            # 缓存委托
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = orderReq.symbol
            order.exchange = EXCHANGE_Coinw
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
            newdic = {
                'api_key': self.apiKey,
                'sign': mysign
            }
            self.addRequest('POST', path,
                            callback=self.onSendOrder,
                            onFailed=self.onSendOrderFailed,
                            onError=self.onSendOrderError,
                            params=newdic,
                            extra=localID)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def cancelOrder(self, cancelReq):
        dic = {
            'api_key': self.apiKey,
            'id' : cancelReq.orderID
            # 'secret_key': self.secretKey
        }
        try:
            mysign = self.generateSignature(**dic)
            # del dic['secret_key']
            dic['sign'] = mysign
            newdic = {
                'api_key': self.apiKey,
                'sign': mysign
            }
            self.addRequest('POST', '/appApi.html?action=cancel_entrust&id=' + cancelReq.orderID, params=newdic,
                            callback=self.onCancelOrder, extra=cancelReq)
        except Exception as e:
            print(e)

    # 取消全部订单
    def cancelAllOrders(self):
        for symbol in self.symbols:
            dic = {
                'api_key': self.apiKey,
                'symbol': self.symbolsKeys[symbol]
                # 'secret_key': self.secretKey
            }
            try:
                mysign = self.generateSignature(**dic)
                # del dic['secret_key']
                dic['sign'] = mysign
                newdic = {
                    'api_key': self.apiKey,
                    'sign': mysign
                }
                self.addRequest('POST', '/appApi.html?action=entrust&symbol=' + self.symbolsKeys[symbol], params=newdic,
                                callback=self.onQueryOpenOrdersAndCancel, extra=symbol)
            except Exception as e:
                print(e)

    def onQueryOpenOrdersAndCancel(self, data, request):
        if data['code'] == 200:
            if data['data'] is None:
                return
            for d in data['data']:
                order = VtOrderData()
                order.orderID = str(d['id'])
                order.gatewayName = self.gatewayName
                order.vtOrderID = '.'.join([order.gatewayName, order.orderID])
                order.exchange = EXCHANGE_Coinw
                order.symbol = request.extra
                order.vtSymbol = '.'.join([order.exchange, order.symbol])

                order.price = float(d['prize'])  # 委托价格
                order.avgprice = float(d['prize'])  # 平均成交价
                order.totalVolume = float(d['count'])  # 委托数量
                order.tradedVolume = float(d['success_count'])  # 成交数量
                order.status = orderStatusMapReverse[str(d['status'])]  # 订单状态
                order.direction = directionMapReverse[d['type']]  # 交易方向   0 买入 1 卖出

                dt = datetime.fromtimestamp(d['createTime']/1000)
                order.orderTime = dt.strftime('%H:%M:%S')

                self.cancelOrder(order)

    # 查询虚拟币对应Symbol和对应交易对
    def getSymbol(self):
        timestamp = int(time.time())
        dic = {
            'api_key': self.apiKey,
            'secret_key':self.secretKey
        }
        try:
            mysign = self.generateSignature(**dic)
            del dic['secret_key']
            dic['sign'] = mysign
            self.addRequest('POST', '/appApi.html?action=getSymbol',
                            callback=self.onGetSymbol)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------------------
    def queryAccount(self):
        timestamp = int(time.time())
        dic = {
            'api_key': self.apiKey
            #'secret_key': self.secretKey
        }
        try:
            mysign = self.generateSignature(**dic)
            #del dic['secret_key']
            dic['sign'] = mysign
            self.addRequest('POST', '/appApi.html?action=userinfo', params=dic,
                            callback=self.onQueryAccount)
        except Exception as e:
            print(e)
            #time.sleep(5)  # 每隔5秒刷新账户信息

    def queryOrder(self, orderid):
        dic = {
            'api_key': self.apiKey,
            'id' : orderid
            # 'secret_key': self.secretKey
        }
        try:
            mysign = self.generateSignature(**dic)
            # del dic['secret_key']
            dic['sign'] = mysign
            newdic = {
                'api_key': self.apiKey,
                'sign': mysign
            }
            self.addRequest('POST', '/appApi.html?action=order&id=' + orderid, params=newdic,
                            callback=self.onQueryOrder)
        except Exception as e:
            print(e)

    # 获取Coinw当前委托
    def queryOpenOrders(self):
        for symbol in self.symbols:
            dic = {
                'api_key': self.apiKey,
                'symbol': self.symbolsKeys[symbol]
                # 'secret_key': self.secretKey
            }
            try:
                mysign = self.generateSignature(**dic)
                # del dic['secret_key']
                dic['sign'] = mysign
                newdic = {
                    'api_key': self.apiKey,
                    'sign': mysign
                }
                self.addRequest('POST', '/appApi.html?action=entrust&symbol=' + self.symbolsKeys[symbol], params=newdic,
                                callback=self.onQueryOpenOrders, extra=symbol)
            except Exception as e:
                print(e)

    # 查询虚拟币对应Symbol和对应交易对
    def onGetSymbol(self, data, request):
        """"""
        if data['code'] == 200:
            self.symbolsList = {}  # '1":'swtc/usdt"
            self.symbolsKeys = {}  # 'swtc/usdt":'1"
            temp = data['data']['交易对symbol'].split('  ')
            for item in temp:
                if ':' in item:
                    self.symbolsList[item.split(':')[0]] = item.split(':')[1]
                    self.symbolsKeys[item.split(':')[1]] = item.split(':')[0]
            print(self.symbolsList)
            self.gateway.writeLog(data['msg'])
        else:
            msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            self.gateway.writeLog(msg)

    def onQueryAccount(self, data, request):
        """"""
        if data['code'] == 200:
            d = data['data']
            for currency in self.coins:
                account = self.accountDict.get(currency, None)

                if not account:
                    account = VtAccountData()
                    account.gatewayName = self.gatewayName
                    account.accountID = currency
                    account.vtAccountID = '.'.join([account.gatewayName, account.accountID])

                    self.accountDict[currency] = account

                account.available = float(d['free'][currency])
                account.margin = float(d['frozen'][currency])

                account.balance = account.margin + account.available

            for account in self.accountDict.values():
                self.gateway.onAccount(account)

            #self.queryOrder()
            #self.queryHistoryOrder()
            #self.gateway.writeLog('资金信息查询成功')
        else:
            msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            self.gateway.writeLog(msg)
            return

    def onQueryOrder(self, data, request):
        if data['code'] == 200:
            try:
                for d in data['data']:
                    orderID = d['id']
                    strOrderID = str(orderID)

                    if strOrderID in self.orderDict.keys():
                        order = self.orderDict[strOrderID]
                        order.gatewayName = self.gatewayName
                        order.vtOrderID = '.'.join([order.gatewayName, order.orderID])
                        order.exchange = EXCHANGE_Coinw
                        order.vtSymbol = '.'.join([order.exchange, order.symbol])

                        order.price = float(d['prize'])  # 委托价格
                        order.avgprice = float(d['prize'])  # 平均成交价
                        order.totalVolume = float(d['count'])  # 委托数量
                        order.tradedVolume = float(d['success_count'])  # 成交数量
                        order.status = orderStatusMapReverse[str(d['status'])]  # 订单状态
                        if order.status != STATUS_CANCELLED:
                            if order.tradedVolume > 0 and order.tradedVolume < order.totalVolume:
                                order.status = STATUS_PARTTRADED
                            elif order.tradedVolume > 0:
                                order.status = STATUS_ALLTRADED
                        order.direction = directionMapReverse[d['type']]   # 交易方向   0 买入 1 卖出

                        dt = datetime.fromtimestamp(data['time']/1000)
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
        if data['code'] == 200:
            data['symbol'] = request.extra
            self.gateway.processQueueOrder(data)
        else:
            msg = '错误信息：%s' % (data['msg'])
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

        if data['code'] != 200:
            msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            self.gateway.writeLog(msg)

            order.status = STATUS_REJECTED
            self.gateway.onOrder(order)
        else:
            order.status = STATUS_ORDERED  # 已报
            strOrderID = str(data['data'])

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
        if data['code'] != 200:
            msg = '错误信息：%s' % (data['msg'])
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
            tick.exchange = EXCHANGE_Coinw
            tick.vtSymbol = '.'.join([tick.exchange, tick.symbol])
            self.tickDict[symbol] = tick
            self.dealDict[symbol] = tick

    def subscribe(self, subscribeReq):
        #depth = 5
        #dealSize = 20
        for symbol in self.symbols:
            # 获取实时深度行情
            path = "/appApi.html?action=depth&symbol=" + self.symbolsKeys[symbol]
            self.addRequest('POST ', path, extra=symbol,
                            callback=self.onDepth,
                            onFailed=self.onFailed,
                            onError=self.onError)
            time.sleep(2)

    # ----------------------------------------------------------------------
    def onTick(self, data, request):
        if data['code'] == 200:
            tick = VtTickData()
            symbol = request.extra
            tick = self.tickDict[symbol]
            tick.lastPrice = float(data['last'])
            tick.highPrice = float(data['high'])
            tick.lowPrice = float(data['low'])
            tick.volume = float(data['vol'])
            tick.buy = data['buy']
            tick.sell = data['sell']

            self.gateway.onTick(tick)
        else:
            msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            self.gateway.writeLog(msg)


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
        if data['code'] != 200:
            msg = '错误代码：%s, 错误信息：%s' % (data['code'], data['msg'])
            self.gateway.writeLog(msg)
        else:
            try:
                symbol = request.extra
                #print('symbol is %s'%(symbol))
                tick = self.tickDict[symbol]

                bids = data['data']['bids']
                asks = data['data']['asks']

                depth = 5
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
                            setattr(tick, para, float(bids[index]['amount']))  # float can sum
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
                            setattr(tick, para, float(asks[index]['amount']))
                except Exception as e:
                    print(e)

                tick.datetime = datetime.fromtimestamp(data['time']/1000)
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

