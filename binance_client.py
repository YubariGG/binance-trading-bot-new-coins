import json
import threading
import time
import random
import copy
from binance.client import Client
from order_handler import Order_handler
from email_model import Email
from datetime import datetime

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
        self.client = Client(
            api_key=credentials["api"], api_secret=credentials["secret"], tld=credentials["tld"])
        # self.client = Client(api_key=credentials["api_test"], api_secret=credentials["secret_test"], tld=credentials["tld"], testnet=True)
        self.order_handler = Order_handler(
            self.client, config["test"], config["pairing"], config["quantity"], config["tp"], config["sl"])
        self.email = Email(
            email_credentials["email"], email_credentials["password"], email_credentials["targets"])

        # Startup routine:
        self.coins = {coin["symbol"]: True for coin in self.client.get_all_tickers()}
        self.new_coins = {}
        self.orders = {}
        self.sell_orders = {}

    def check_new_coins(self, sleep=1):
        while True:
            # API call:
            current_coins = self.client.get_all_tickers()
            self.current_coins = current_coins
            current_coins_length = len(current_coins)

            # Main logic of the thread:
            if current_coins_length > len(self.coins):
                for coin in current_coins:
                    if coin["symbol"] not in self.coins:
                        self.coins[coin["symbol"]] = True

                        # Add the buyable coin to reduce overhead:
                        if self.pairing in coin["symbol"]:
                            self.new_coins[coin["symbol"]
                                           ] = float(coin["price"])

            time.sleep(sleep)

    def check_current_pool(self):
        time.sleep(1) # To avoid faster execution than check new coins
        while True:
            initial_coins = copy.deepcopy(self.coins)
            for initial_coin in initial_coins.keys():
                located_coin = list(filter(lambda coin: coin["symbol"] == initial_coin, self.current_coins))
                if len(located_coin) > 1:
                    del self.coins[initial_coin]


    def write_current_coin_pool(self):
        print(datetime.now().strftime("%H:%M"))
        while True:
            if datetime.now().strftime("%H:%M") == "00:00":
                with open("current_coin_pool.json", "w") as file:
                    file.write(json.dumps(self.coins))

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
                            <li><strong>{symbol}</strong>: bought {float(order['executedQty']):.3f} for {float(order['cummulativeQuoteQty']):.3f} USDT at a price of <strong>{order['price']}</strong> USDT. Including the commision fee we have a volume of <strong>{order['vol2trade']}</strong> {symbol} to trade with.</li>
                        """
                    body += "</ul>"
                    self.email.send(body, "Testeando funcionalidad")

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
                    body = "<p>Sell order placed for the following coins:</p><ul>"
                    for symbol, order in sell_orders.items():
                        body += f"""
                            <li><strong>{symbol}</strong>: sold <strong>{float(order['realQuote']):.3f}</strong> {symbol} for {order['price']} USDT. A margin of {float(order['margin']):.3f} USDT was made with the current transaction.</li>
                        """
                    body += "</ul>"
                    self.email.send(body, "Sell order placed")


    def main(self):
        # Writer daemon:
        threading.Thread(target=self.write_transactions, daemon=True).start()
        threading.Thread(target=self.write_current_coin_pool, daemon=True).start()

        # Scanner daemon configuration:
        for sleep in self.sleep:
            threading.Thread(target=self.check_new_coins, args=(sleep,), daemon=True).start()
        threading.Thread(target=self.check_current_pool, daemon=True).start()

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
                        updt_sl = current_price < (buyout_price + buyout_price * order["sl"] / 100)
                        sell_sl = current_price < (buyout_price - buyout_price * self.sl / 100)
                        sell_tp = current_price > (buyout_price + buyout_price * self.tp / 100)

                        if updt_tp and self.enable_tsl:
                            # Update TP:
                            new_tp = current_price + current_price * self.ttp / 100
                            new_tp = (new_tp - buyout_price) / buyout_price * 100
                            # Update SL:
                            new_sl = current_price - current_price * self.tsl / 100
                            new_sl = (new_sl-buyout_price) / buyout_price * 100
                            # Update order:
                            self.orders[symbol]["tp"] = new_tp
                            self.orders[symbol]["sl"] = new_sl

                        elif (sell_sl or updt_sl) or (sell_tp and not self.enable_tsl):
                            self.sell_orders.update(self.order_handler.sell(order))
                            del self.orders[symbol]

            except Exception as e:
                self.email.send(
                    f"<p>Main routine failed due to the following reasons:</p><p>{e}</p>", "ERROR")
                break


if __name__ == "__main__":
    binance = BinanceHandler()
    binance.main()
