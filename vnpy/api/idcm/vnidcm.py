# encoding: UTF-8

from __future__ import print_function
import hashlib
import hmac
import json
import ssl
import traceback

from threading import Thread

import websocket
from six.moves import input


WEBSOCKET_HOST = 'wss://real.IDCM.cc:10030/websocket'

    
########################################################################
class IdcmWebsocketApi(object):
    """Websocket API"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.ws = None
        self.thread = None
        self.active = False
    
    #----------------------------------------------------------------------
    def start(self):
        """启动"""
        self.ws = websocket.create_connection(WEBSOCKET_HOST,
                                              sslopt={'cert_reqs': ssl.CERT_NONE})
    
        self.active = True
        self.thread = Thread(target=self.run)
        self.thread.start()
        
        self.onConnect()
    
    #----------------------------------------------------------------------
    def reconnect(self):
        """重连"""
        self.ws = websocket.create_connection(WEBSOCKET_HOST,
                                              sslopt={'cert_reqs': ssl.CERT_NONE})   
        
        self.onConnect()
        
    #----------------------------------------------------------------------
    def run(self):
        """运行"""
        while self.active:
            try:
                stream = self.ws.recv()
                data = json.loads(stream)
                self.onData(data)
            except:
                msg = traceback.format_exc()
                self.onError(msg)
                self.reconnect()
    
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.active = False
        
        if self.thread:
            self.thread.join()
        
    #----------------------------------------------------------------------
    def onConnect(self):
        """连接回调"""
        #print('connected')
    
    #----------------------------------------------------------------------
    def onData(self, data):
        """数据回调"""
        print('-' * 30)
        l = data.keys()
        l.sort()
        for k in l:
            print(k, data[k])
    
    #----------------------------------------------------------------------
    def onError(self, msg):
        """错误回调"""
        print(msg)
    
    #----------------------------------------------------------------------
    def sendReq(self, req):
        """发出请求"""
        self.ws.send(json.dumps(req))      




"""
if __name__ == '__main__':
    from datetime import datetime
    from time import sleep
    
    API_KEY = '88893f839fbd49f4b5fcb03e7c15c015'
    API_SECRET = 'ef383295cf4e4c128e6d18d7e9564b12'
    
    # REST测试
    rest = FcoinRestApi()
    rest.init(API_KEY, API_SECRET)
    rest.start(3)
       
    #rest.addReq('GET', '/accounts/balance', rest.onData)
    
    # 查委托
    #states = ['submitted', 'partial_filled', 'partial_canceled', 
              #'filled', 'canceled', 'pending_cancel']    
    #req = {
        #'symbol': 'ethusdt',
        #'start': datetime.now().strftime('%Y%m%d'),
        #'states': 'submitted',
        #'limit': 500        
    #}
    
    #for i in range(10):
        #rest.addReq('GET', '/orders', rest.onData, params=req)
        #sleep(2)
        
    req = {
        'symbol': 'ethusdt',
        'side': 'buy',
        'type': 'limit',
        'price': 300,
        'amount': 0.01
    }    
    rest.addReq('POST', '/orders', rest.onData, postdict=req)
    #sleep(1)
    #rest.addReq('POST', '/orders', rest.onData, params=req)

    ## WS测试
    #ws = FcoinWebsocketApi()
    #ws.start()
    
    #req = {
        #'cmd': 'sub',
        #'args': ['depth.L20.btcusdt'],
        #'id': 1
    #}
    
    #ws.sendReq(req)

    input()
"""
    
