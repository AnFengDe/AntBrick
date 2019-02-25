# encoding: UTF-8

'''
本文件中实现了风控引擎，用于提供一系列常用的风控功能：
1. 委托流控（单位时间内最大允许发出的委托数量）
2. 总成交限制（每日总成交数量限制）
3. 单笔委托的委托数量控制
'''

from __future__ import division

import json
import os
import platform

from vnpy.event import Event
from vnpy.trader.vtEvent import *
from vnpy.trader.vtConstant import *
from vnpy.trader.vtGateway import VtLogData
from vnpy.trader.vtFunction import getJsonPath


########################################################################
class RmEngine(object):
    """风控引擎"""
    settingFileName = 'RM_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    name = u'风控模块'

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        # 绑定自身到主引擎的风控引擎引用上
        mainEngine.rmEngine = self

        # 是否启动风控
        self.active = False

        self.orderFlowClear = EMPTY_INT  # 计数清空时间（秒）
        self.orderFlowTimer = EMPTY_INT     # 计数清空时间计时
        """
        # 流控相关
        self.orderFlowCount = EMPTY_INT     # 单位时间内委托计数
        self.orderFlowLimit = EMPTY_INT     # 委托限制
                
        # 单笔委托相关
        self.orderSizeLimit = EMPTY_INT     # 单笔委托最大限制

        # 成交统计相关
        self.tradeCount = EMPTY_INT         # 当日成交数量统计
        self.tradeLimit = EMPTY_INT         # 当日成交合约数量限制

        # 单品种撤单统计
        self.orderCancelLimit = EMPTY_INT   # 撤单总次数限制
        self.orderCancelDict = {}           # 单一合约对应撤单次数的字典

        # 活动合约相关
        self.workingOrderLimit = EMPTY_INT  # 活动合约最大限制
        # 保证金相关
        self.marginRatioDict = {}           # 保证金占账户净值比例字典
        self.marginRatioLimit = EMPTY_FLOAT # 最大比例限制
        """
        self.settingsDict = {}
        self.accountAvailable = {}  # 每个账户最新可用余额

        self.loadSetting()
        self.registerEvent()

    #----------------------------------------------------------------------
    def loadSetting(self):
        """读取配置"""
        with open(self.settingFilePath) as f:
            d = json.load(f)

            # 设置风控参数
            #self.active = d['active']
            #self.warnLimit = d['warnLimit']  # 报警值

            #self.symbolSettingDict=[]  # 交易对阈值

            """
            self.orderFlowLimit = d['orderFlowLimit']
            self.orderFlowClear = d['orderFlowClear']
            self.orderSizeLimit = d['orderSizeLimit']
            self.tradeLimit = d['tradeLimit']
            self.workingOrderLimit = d['workingOrderLimit']
            self.orderCancelLimit = d['orderCancelLimit']           
            self.marginRatioLimit = d['marginRatioLimit']
            """
            for key in d.keys():
                self.settingsDict[key] = d[key]

    #----------------------------------------------------------------------
    def saveSetting(self):
        """保存风控参数"""
        with open(self.settingFilePath, 'w') as f:
            # 写入json
            jsonD = json.dumps(self.settingsDict, indent=4)
            #jsonD = json.dumps(d, indent=4)
            f.write(jsonD)

    #----------------------------------------------------------------------
    def registerEvent(self):
        """注册事件监听"""
        #self.eventEngine.register(EVENT_TRADE, self.updateTrade)
        self.eventEngine.register(EVENT_TIMER, self.updateTimer)
        #self.eventEngine.register(EVENT_ORDER, self.updateOrder)
        self.eventEngine.register(EVENT_ACCOUNT, self.updateAccount)
        
    #----------------------------------------------------------------------
    def updateOrder(self, event):
        """更新成交数据"""
        # 只需要统计撤单成功的委托
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
    def updateAccount(self, event):
        """账户资金更新"""
        account = event.dict_['data']

        def prn_obj(obj):
            print(', '.join(['%s:%s' % item for item in obj.__dict__.items()]))
            #print('\n')
        #prn_obj(account)
        
        # 更新到字典中
        self.accountAvailable[account.vtAccountID] = account.available

    #----------------------------------------------------------------------
    def writeRiskLog(self, content):
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
    def checkRisk(self, orderReq, gatewayName):
        """检查风险"""
        # 如果没有启动风控检查，则直接返回成功
        if not self.active:
            return True

        # 取得需要使用的账户代币名称
        if orderReq.direction == "卖出":
            symbol = orderReq.symbol.split('-')[0] # '-'为交易对分割符,可能有其他分隔符
        else:
            symbol = orderReq.symbol.split('-')[1]
        accountIndex = gatewayName + "." + symbol

          # gateway.symbol
        if accountIndex not in self.settingsDict.keys():
            self.writeRiskLog(u'账户%s限额配置缺失，请检查，报警' % accountIndex)
            return False

        if (self.accountAvailable[accountIndex] - orderReq.volume) < float(self.settingsDict[accountIndex]['warnLimit']):
            self.writeRiskLog(u'账户%s余额低，报警' %accountIndex)
        if (self.accountAvailable[accountIndex] - orderReq.volume) < float(self.settingsDict[accountIndex]['minLimit']):
            self.writeRiskLog(u'账户%s余额不足，委托拒绝' %accountIndex)
            return False
        # 对于通过风控的委托，增加流控计数
        self.orderFlowCount += 1
        self.accountAvailable[accountIndex] -= orderReq.volume  # 通过风控，余额扣减
        return True

    #----------------------------------------------------------------------
    def clearOrderFlowCount(self):
        """清空流控计数"""
        self.orderFlowCount = 0
        self.writeRiskLog(u'清空流控计数')

    #----------------------------------------------------------------------
    def clearTradeCount(self):
        """清空成交数量计数"""
        self.tradeCount = 0
        self.writeRiskLog(u'清空总成交计数')

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
        """开关风控引擎"""
        self.active = not self.active

        if self.active:
            self.writeRiskLog(u'风险管理功能启动')
        else:
            self.writeRiskLog(u'风险管理功能停止')
            
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        self.saveSetting()
        
