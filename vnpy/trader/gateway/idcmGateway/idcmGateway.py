# encoding: UTF-8

'''
IDCM交易接口
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
#from vnpy.api.websocket import WebsocketClient
from vnpy.api.idcm import IdcmWebsocketApi
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

#from threading import Thread

REST_HOST = 'https://api.IDCM.cc:8323'
WEBSOCKET_HOST = 'wss://real.idcm.cc:10330/websocket'
EXCHANGE_IDCM = "IDCM"

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
errMsgMap[10005] = 'SecretKey不存在'
errMsgMap[10006] = 'Api_key不存在'
errMsgMap[10007] = '签名不匹配'
errMsgMap[10017] = 'API鉴权失败'

errMsgMap[41000] = '签名不匹配'
errMsgMap[41017] = 'API鉴权失败'

errMsgMap[51003] = '账号被冻结'
errMsgMap[51004] = '用户不存在'
errMsgMap[51011] = '交易品种不存在'

errMsgMap[51018] = '虚拟币不存在'
errMsgMap[51022] = '申请数量太少'
errMsgMap[51021] = '虚拟币资产信息不足'
errMsgMap[51023] = '可用数量不足'
errMsgMap[51026] = '数据不存在'
errMsgMap[51027] = '提币申请状态只有在，申请状态才能撤销'

errMsgMap[51040] = '货币资产信息不存在'
errMsgMap[51041] = '现金资产不足'
errMsgMap[51043] = '申报价无效'
errMsgMap[51044] = '申报数量无效'
errMsgMap[51045] = '最小交易量无效'
errMsgMap[51046] = '最小金额无效'
errMsgMap[51047] = '金额变动量无效'
errMsgMap[51048] = '最小申报变动量无效'

errMsgMap[51089] = '非法的站点'
errMsgMap[51092] = '访问过快'
errMsgMap[51111] = '钱包余额不足'
errMsgMap[51112] = '申报金额无效'


def getErrMsg(errcode):
    return errMsgMap[errcode]
    msg = '错误代码：%s, 错误信息：%s' % (data['code'], errMsg)
    self.gateway.writeLog(msg)

"""
# input idcm_sub_spot_BTC-USDT_depth_5
# output BTC-USDT
def getSymbolFromChannel(channel):
    start = channel.find("spot_")
    start += len("spot_")
    end = channel.find("_", start)
    return channel[start:end]
"""


class IdcmGateway(VtGateway):
    """IDCM接口"""

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

        self.restApi = IdcmRestApi(self)
        self.wsApi = WebsocketApi(self)

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
        self.wsApi.connect(apiKey, secretKey, symbols)

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

    def cancelAllOrders(self):
        """全部撤单"""
        self.restApi.cancelAllOrders()

    # ----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.restApi.stop()
        self.wsApi.close()

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

    def processQueueOrder(self, data, historyFlag):
        for d in data['data']:
            # self.gateway.localID += 1
            # localID = str(self.gateway.localID)

            order = VtOrderData()
            order.gatewayName = self.gatewayName

            order.symbol = d['symbol']
            order.exchange = 'IDCM'
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


class IdcmRestApi(RestClient):
    """REST API实现"""
    # ----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super().__init__()

        self.gateway = gateway  # type: IdcmGateway # gateway对象
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

        #self.queryAccountThread = None

    # ----------------------------------------------------------------------
    def sign(self, request):
        """IDCM的签名方案"""
        if request.data:
            request.data = json.dumps(request.data)

        inputdata = request.data
        signature = self.generateSignature(inputdata, self.secretKey)

        # 添加表头
        request.headers = {
            'X-IDCM-APIKEY': self.apiKey,
            'X-IDCM-SIGNATURE': signature,
            'X-IDCM-INPUT': inputdata,
            'Content-Type': 'application/json'
        }
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
        self.queryAccount()
        #self.queryHistoryOrder()

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
            #order.exchange = 'IDCM'
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

    # 获取IDCM最新币币行情数据
    def queryTicker(self):
        """"""
        self.addRequest('POST', path = '/api/v1/getticker', data={"Symbol": "BTC/USDT"},
            callback=self.onqueryTicker)

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

    # 获取IDCM历史订单信息，只返回最近7天的信息
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
                    order.exchange = EXCHANGE_IDCM
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


########################################################################
class WebsocketApi(IdcmWebsocketApi):
    def __init__(self, gateway):
        """Constructor"""
        super().__init__()

        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.apiKey = ''
        self.secretKey = ''
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
        """重载"""
        return json.loads(zlib.decompress(data, -zlib.MAX_WBITS))

    # ----------------------------------------------------------------------
    def connect(self, apiKey, secretKey, symbols):
        """"""
        self.apiKey = apiKey
        self.secretKey = secretKey
        self.symbols = symbols

        self.start()
        #for symbol in symbols:
        #    self.subscribeMarketData(symbol)

    """
    def subscribeMarketData(self, symbol):
        # 订阅行情
        tick = VtTickData()
        tick.gatewayName = self.gatewayName
        tick.symbol = symbol
        tick.exchange = "IDCM"
        tick.vtSymbol = '.'.join([tick.symbol, tick.exchange])
        self.tickDict[symbol] = tick
    """

    def onConnect(self):
        """连接回调"""
        self.gateway.writeLog('Websocket API连接成功')
        self.login()

    def onData(self, data):
        """数据回调"""
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
        """连接回调"""
        self.gateway.writeLog('Websocket API连接断开')

    # ----------------------------------------------------------------------
    def onPacket(self, packet):
        """数据回调"""
        d = packet[0]

        channel = d['channel']
        callback = self.callbackDict.get(channel, None)
        if callback:
            callback(d)

    @staticmethod
    def sign(apiKey, secretkey):
        # 拼接apikey = {你的apikey} & secret_key = {你的secretkey} 进行MD5，结果大写
        convertStr = "apikey=" + apiKey + "&secret_key=" + secretkey
        return hashlib.md5(convertStr.encode()).hexdigest().upper()

    def login(self):
        try:
            signature = self.sign(self.apiKey, self.secretKey)
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
            tick.exchange = EXCHANGE_IDCM
            tick.vtSymbol = '.'.join([tick.exchange, tick.symbol])
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
        """"""
        data = d['data']

        symbol = d['channel'].split('_')[3]
        tick = self.tickDict[symbol]
        tick.lastPrice = float(data['last'])
        tick.highPrice = float(data['high'])
        tick.lowPrice = float(data['low'])
        tick.volume = float(data['vol'])

        self.gateway.onTick(tick)

    def onDeals(self, d):
        """"""
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

    """
    # ----------------------------------------------------------------------
    def onTrade(self, d):
        data = d['data']
        order = self.orderDict.get(str(data['orderid']), None)
        if not order:
            currency = data['contract_name'][:3]
            expiry = str(data['contract_id'])[2:8]

            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = '%s-USD-%s' % (currency, expiry)
            order.exchange = 'IDCM'
            order.vtSymbol = '.'.join([order.symbol, order.exchange])

            restApi = self.gateway.restApi
            restApi.orderID += 1
            order.orderID = str(restApi.loginTime + restApi.orderID)
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
            order.orderTime = data['create_date_str'].split(' ')[-1]
            order.price = data['price']
            order.totalVolume = int(data['amount'])
            order.direction, order.offset = typeMapReverse[str(data['type'])]

            self.localRemoteDict[order.orderID] = str(data['orderid'])
            self.orderDict[str(data['orderid'])] = order

        volumeChange = int(data['deal_amount']) - order.tradedVolume

        order.status = statusMapReverse[str(data['status'])]
        order.tradedVolume = int(data['deal_amount'])
        self.gateway.onOrder(copy(order))

        if volumeChange:
            self.tradeID += 1

            trade = VtTradeData()
            trade.gatewayName = order.gatewayName
            trade.symbol = order.symbol
            trade.exchange = order.exchange
            trade.vtSymbol = order.vtSymbol

            trade.orderID = order.orderID
            trade.vtOrderID = order.vtOrderID
            trade.tradeID = str(self.tradeID)
            trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])

            trade.direction = order.direction
            trade.offset = order.offset
            trade.volume = volumeChange
            trade.price = float(data['price_avg'])
            trade.tradeTime = datetime.now().strftime('%H:%M:%S')
            self.gateway.onTrade(trade)


    # ----------------------------------------------------------------------
    def onPosition(self, d):
        data = d['data']

        for buf in data['positions']:
            position = VtPositionData()
            position.gatewayName = self.gatewayName

            currency = buf['contract_name'][:3]
            expiry = str(buf['contract_id'])[2:8]
            position.symbol = '%s-USD-%s' % (currency, expiry)
            position.exchange = 'OKEX'
            position.vtSymbol = '.'.join([position.symbol, position.exchange])
            position.position = int(buf['hold_amount'])
            position.frozen = int(buf['hold_amount']) - int(buf['eveningup'])
            position.price = float(buf['avgprice'])

            if buf['position'] == 1:
                position.direction = DIRECTION_LONG
            else:
                position.direction = DIRECTION_SHORT
            position.vtPositionName = '.'.join([position.vtSymbol, position.direction])
            self.gateway.onPosition(position)


symbolMap = {}  # 代码映射v3 symbol:(v1 currency, contractType)


# ----------------------------------------------------------------------
def convertSymbol(symbol3):
    # 转换代码
    if symbol3 in symbolMap:
        return symbolMap[symbol3]

    # 拆分代码
    currency, usd, expire = symbol3.split('-')

    # 计算到期时间
    expireDt = datetime.strptime(expire, '%y%m%d')
    now = datetime.now()
    delta = expireDt - now

    # 根据时间转换
    if delta <= timedelta(days=7):
        contractType = 'this_week'
    elif delta <= timedelta(days=14):
        contractType = 'next_week'
    else:
        contractType = 'quarter'

    result = (currency.lower(), contractType)
    symbolMap[symbol3] = result
    return result


# ----------------------------------------------------------------------
def printDict(d):
    print('-' * 30)
    l = d.keys()
    l.sort()
    for k in l:
        print(k, d[k])

"""