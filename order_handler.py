import time
import random


class Order_handler:
    def __init__(self, client, test, pairing, quantity, tp, sl):
        self.client = client
        self.test = test
        self.pairing = pairing
        self.quantity = quantity
        self.tp = tp
        self.sl = sl

    def get_decimals(self, coin):
        info = self.client.get_symbol_info(coin)
        return info['filters'][2]['stepSize'].index("1") - 1
        
    def correct_volume(self, quantity, decimals, price=None):
        if price: quantity = quantity / price
        if decimals < 0:
            return str(int(quantity))
        else:
            return "{:.{}f}".format(quantity, decimals)

    def buy(self, coin, price):
        decimals = self.get_decimals(coin)
        quantity = self.correct_volume(self.quantity, decimals, price)
        order = {coin:{"decimals":decimals, "volume":quantity}}
        if self.test:
            print("Running buying in test mode")
            order[coin].update(self.buy_order_test(coin, quantity, price))
        else:
            order[coin].update(self.client.create_order(
                symbol=coin,
                side="BUY",
                type="MARKET",
                quantity=quantity     
            ))

        # Evaluate how much we lost in the commision:
        order[coin]["adqQty"] = sum(map(lambda action: float(action["qty"]) - float(action["commission"]), order[coin]["fills"]))
        order[coin]["price"] = float(order[coin]["cummulativeQuoteQty"]) / float(order[coin]["executedQty"])
        order[coin]["vol2trade"] = self.correct_volume(order[coin]["adqQty"], decimals)
        order[coin]["tp"] = self.tp
        order[coin]["sl"] = self.sl
        order[coin]["write"] = True
        return order

    def buy_order_test(self, coin, quantity, price):
        return {
            "symbol": coin,
            "orderId": random.randint(10000, 99999),
            "orderListId": -1,
            "ClientOrderId": "98sd7fsd98fs9sdf",
            "transactTime": int(time.time()*1000),
            "origQty": quantity,
            "executedQty": quantity,
            "cummulativeQuoteQty":str(price*float(quantity)),
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": "MARKET",
            "side": "BUY",
            "fills": [
                    {
                        "price": str(price),
                        "qty": quantity,
                        "commission": str(float(quantity) * 0.01),
                        "commissionAsset": coin.split(self.pairing)[0],
                        "tradeId": random.randint(10000, 99999)
                    }
                ]
        }

    def sell(self, order):
        symbol = order["symbol"]
        if self.test:
            print("Running selling in test mode")
            sell_order = {symbol:self.sell_order_test(order)}
        else:
            sell_order = {symbol:self.client.create_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=order["vol2trade"]
            )}
        sell_order[symbol]["realQuote"] = sum(map(lambda action: float(action["price"]) * (float(action["qty"]) - float(action["commission"])), sell_order[symbol]["fills"]))
        sell_order[symbol]["margin"] = sell_order[symbol]["realQuote"] - order["cummulativeQuoteQty"]
        sell_order[symbol]["write"] = True
        return sell_order

    def sell_order_test(self, order):
        price = self.client.get_ticker(symbol=order["symbol"])["lastPrice"]
        order["transactTime"] = int(time.time()*1000)
        order["cummulativeQuoteQty"] = float(order["vol2trade"]) * float(price)
        order["origQty"] = order["vol2trade"]
        order["executedQty"] = order["vol2trade"]
        order["side"] = "SELL"
        order["fills"] = [
                {
                    "price": price,
                    "qty": order["vol2trade"],
                    "commission": str(float(order["vol2trade"]) * 0.01),
                    "commissionAsset": self.pairing,
                    "tradeId": random.randint(10000, 99999)
                }
            ]
        return order

if __name__ == '__main__':
    from binance.client import Client
    import json

    # Loading the credentials:
    with open("auth.json", "r") as file:
        credentials = json.loads(file.read())

    with open("config.json", "r") as file:
        config = json.loads(file.read())

    # Generating the classes
    client = Client(api_key=credentials["api"], api_secret=credentials["secret"], tld=credentials["tld"])
    orders = Order_handler(client, config["test"], config["pairing"], config["quantity"], config["tp"], config["sl"])

    # Testing functionality
    test_coin = "CHESSUSDT"
    price = client.get_ticker(symbol=test_coin)["lastPrice"]
    order = orders.buy(test_coin, float(price))
    print(order)
    time.sleep(1)
    sell = orders.sell(order[test_coin])
    print(f'Margin: {sell[test_coin]["margin"]:.3f} {config["pairing"]}')

