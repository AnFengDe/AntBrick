# 从coinbase.pro获取最新的比特币价格
""" 调用接口
连接 CoinbaseWatch.connect()
获取最新成交价  Coinbase CoinbaseWatch.getLatestPrice()
断开            Coinbase CoinbaseWatch.stop()
"""
import time
import cbpro


class CoinbaseWatch(object):
    def connect(self):
        self.wsClient = CoinbaseWebsocketClient()
        self.wsClient.channels=['matches']  # 订阅成交回报
        self.wsClient.start()

    def getLatestPrice(self):
        return self.wsClient.latestprice

    def stop(self):
        if hasattr(self, 'wsClient'):
            self.wsClient.close()


class CoinbaseWebsocketClient(cbpro.WebsocketClient):
    def on_open(self):
        #self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = ["BTC-USD"]
        print("Connected on coinbase Websocket")
        self.latestprice = 0

    def on_message(self, msg):
        if msg['type'] == 'last_match':
            self.latestprice = msg["price"]
        elif msg['type'] =='match':
            #print ("Message type:", msg["type"], "size:", msg["size"], "price",
            #    "\t{:.3f}".format(float(msg["price"])), "trade_id: ", msg["trade_id"],
            #    "time:" , msg["time"])
            self.latestprice = msg["price"]
        else:
            print(msg)
        #print(self.lastprice)

    def on_close(self):
        print("-- Goodbye! --")


def test():
    loopcount = 0
    while loopcount < 100:
        btcDatagateway = CoinbaseWatch()
        btcDatagateway.connect()
        time.sleep(3)
        price = btcDatagateway.getLatestPrice()
        if price == 0:
            print('price is 0')
            print('sleep 2')
            time.sleep(2)
            price = btcDatagateway.getLatestPrice()
        print(price)
        btcDatagateway.stop()
        loopcount += 1