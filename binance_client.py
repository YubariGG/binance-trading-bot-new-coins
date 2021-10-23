import json
import threading
import time
import random
import copy
from binance.client import Client
from order_handler import Order_handler
from email_model import Email

# Loading the credentials:
with open("auth.json", "r") as file:
    credentials = json.loads(file.read())

with open("email_credentials.json", "r") as file:
    email_credentials = json.loads(file.read())

# Loading the configuration:
with open("config.json", "r") as file:
    config = json.loads(file.read())


class BinanceHandler:
    def __init__(self):
        # Class config:
        self.pairing = config["pairing"]
        self.tp = config["tp"]
        self.sl = config["sl"]
        self.ttp = config["ttp"]
        self.tsl = config["tsl"]
        self.enable_tsl = config["enable_tsl"]
        self.test = config["test"]

        # Threading config:
        self.threads = 5
        self.sleep = [0.1*random.random() for _ in range(5)]

        # Classes initialization:
        self.client = Client(api_key=credentials["api"], api_secret=credentials["secret"], tld=credentials["tld"])
        self.order_handler = Order_handler(self.client, config["test"], config["pairing"], config["quantity"], config["tp"], config["sl"])
        self.email = Email(email_credentials["email"], email_credentials["password"], email_credentials["targets"])

        # Startup routine:
        self.coins = {coin["symbol"]: True for coin in self.client.get_all_tickers()}
        self.new_coins = {}
        self.orders = {}
        self.sell_orders = {}

    def check_new_coins(self, sleep=1):
        while True:
            # API call:
            current_coins = self.client.get_all_tickers()
            current_coins_length = len(current_coins)

            # Main logic of the thread:
            if current_coins_length > len(self.coins):
                for coin in current_coins:
                    if coin["symbol"] not in self.coins:
                        self.coins[coin["symbol"]] = True

                        # Add the buyable coin to reduce overhead:
                        if self.pairing in coin["symbol"]:
                            self.new_coins[coin["symbol"]] = float(coin["price"])

            time.sleep(sleep)

    def write_transactions(self):
        while True:
            if len(self.orders) > 0:
                orders = copy.deepcopy(self.orders)
                for symbol, order in self.orders.items():
                    if order["write"]:
                        order["write"] = False
                    else:
                        del orders[symbol]
                if len(orders) > 0:
                    with open("orders.json", "w") as file:
                        file.write(json.dumps(orders))
                    body = "<p>Buy order placed for the following coins:</p><ul>"
                    for symbol, order in orders.items():
                        body += f"""
                            <li><strong>{symbol}</strong>: bought {float(order['executedQty']):.2f} for {order['cummulativeQuoteQty']} USDT at a price of <strong>{order['price']}</strong> USDT. Including the commision fee we have a volume of <strong>{order['vol2trade']}</strong> {symbol} to trade with.</li>
                        """
                    body += "</ul>"
                    self.email.send(body, "Estoy probando el nuevo bot.")

            if len(self.sell_orders) > 0:
                sell_orders = copy.deepcopy(self.sell_orders)
                for symbol, sell_order in self.sell_orders.items():
                    if sell_order["write"]:
                        sell_order["write"] = False
                    else:
                        del sell_orders[symbol]
                if len(sell_orders) > 0:
                    with open("sell_orders.json", "w") as file:
                        file.write(json.dumps(sell_orders))

    def main(self):
        # Writer daemon:
        writer = threading.Thread(target=self.write_transactions)
        writer.daemon = True
        writer.start()

        # Scanner daemon configuration:
        for sleep in self.sleep:
            watcher = threading.Thread(
                target=self.check_new_coins, args=(sleep,))
            watcher.daemon = True
            watcher.start()

        t0 = time.time()
        del self.coins['CHESSUSDT']
        del self.coins['LAZIOUSDT']
        # Main logic of the trading algorithm 
        while True:
            try:
                # Buying logic:
                if len(self.new_coins) > 0:
                    new_coins = copy.deepcopy(self.new_coins)
                    for new_coin, new_coin_price in new_coins.items():
                        self.orders.update(self.order_handler.buy(new_coin, new_coin_price))
                        del self.new_coins[new_coin]

                # Selling logic:
                if len(self.orders) > 0:
                    orders = copy.deepcopy(self.orders)
                    for symbol, order in orders.items():
                        buyout_price = order["price"]
                        current_price = float(self.client.get_ticker(symbol=symbol)["lastPrice"])

                        # Conditions:
                        updt_tp = current_price > (buyout_price + buyout_price * order["tp"] / 100)
                        sell_sl = current_price < (buyout_price - buyout_price * self.sl / 100)
                        sell_tp = current_price > (buyout_price + buyout_price * self.tp / 100)

                        if updt_tp and self.enable_tsl:
                            new_tp = current_price + current_price * self.ttp / 100
                            new_tp = (new_tp - buyout_price) / buyout_price * 100
                            self.orders[symbol]["tp"] = new_tp

                        elif sell_sl or (sell_tp and not self.enable_tsl):
                            self.sell_orders.update(self.order_handler.sell(order))
                            del self.orders[symbol]

                if time.time() - t0 > 20:
                    break

            except Exception as e:
                self.email.send(f"<p>Main routine failed due to the following reasons:</p><p>{e}</p>", "ERROR")
                break

        print(self.sell_orders)



if __name__ == "__main__":
    binance = BinanceHandler()
    binance.main()