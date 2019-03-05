# encoding: UTF-8

# 重载sys模块，设置默认字符串编码方式为utf8
#try:
#    reload         # Python 2
#except NameError:  # Python 3
#    from importlib import reload
import sys
#reload(sys)
#sys.setdefaultencoding('utf8')

# vn.trader模块
from vnpy.event import EventEngine
from vnpy.trader.vtEngine import MainEngine
from vnpy.trader.uiQt import createQApp

# 加载底层接口
from vnpy.trader.gateway import (jccGateway)
                                 #idcmGateway)
                                #(huobiGateway, okexGateway, okexfGateway,
                                 #binanceGateway, bitfinexGateway,
                                 #bitmexGateway, fcoinGateway,
                                 #bigoneGateway,
                                 #lbankGateway,
                                 #coinbaseGateway, ccxtGateway)

# 加载上层应用
#from vnpy.trader.app import (algoTrading)
from vnpy.trader.app.alGo import (followBtcSelfTrade)  # 跟随BTC刷单交易
from vnpy.trader.app import (riskManager)  # 风控模块
#from vnpy.trader.app import (dataRecorder)
#from vnpy.trader.app import (optionMaster)
#from vnpy.trader.app import (rpcService)
#from vnpy.trader.app import (rtdService)
#from vnpy.trader.app import (spreadTrading)
#from vnpy.trader.app import (tradeCopy)

# 当前目录组件
from uiCryptoWindow import MainWindow


def main():
    """主程序入口"""
    # 创建Qt应用对象
    qApp = createQApp()

    # 创建事件引擎
    ee = EventEngine()

    # 创建主引擎
    me = MainEngine(ee)

    # 添加交易接口
    #me.addGateway(okexfGateway)
    #me.addGateway(ccxtGateway)
    #me.addGateway(coinbaseGateway)
    #me.addGateway(lbankGateway)
    #me.addGateway(bigoneGateway)
    #me.addGateway(fcoinGateway)
    #me.addGateway(bitmexGateway)
    #me.addGateway(huobiGateway)
    #me.addGateway(okexGateway)
    #me.addGateway(binanceGateway)
    #me.addGateway(bitfinexGateway)
    me.addGateway(jccGateway)
    #me.addGateway(idcmGateway)

    # 添加上层应用
#    me.addApp(algoTrading)
    me.addApp(followBtcSelfTrade)
    me.addApp(riskManager)
#    me.addApp(dataRecorder)
#    me.addApp(optionMaster)
    #me.addApp(rpcService)
#    me.addApp(rtdService)
#    me.addApp(spreadTrading)

    # 创建主窗口
    mw = MainWindow(me, ee)
    mw.showMaximized()

    # 在主线程中启动Qt事件循环
    sys.exit(qApp.exec_())


if __name__ == '__main__':
    main()
