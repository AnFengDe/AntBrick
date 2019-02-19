# 从coinbase.pro获取最新的比特币价格
import cbpro, time


class coinbaseClient(object):
    def connect(self):
        self.wsClient = myWebsocketClient()
        self.wsClient.channels=['matches']  # 订阅成交回报
        self.wsClient.start()

    def getLastPrice(self):
        return self.wsClient.lasprice

    def stop(self):
        self.wsClient.stop()


class myWebsocketClient(cbpro.WebsocketClient):
    def on_open(self):
        #self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = ["BTC-USD"]
        print("Connected on coinbase Websocket")
        self.lastprice = 0

    def on_message(self, msg):
        if msg['type'] == 'last_match':
            self.lastprice = msg["price"]
        elif msg['type'] =='match':
            #print ("Message type:", msg["type"], "size:", msg["size"], "price",
            #    "\t{:.3f}".format(float(msg["price"])), "trade_id: ", msg["trade_id"],
            #    "time:" , msg["time"])
            self.lastprice = msg["price"]
        else:
            print(msg)
        #print(self.lastprice)

    def on_close(self):
        print("-- Goodbye! --")



