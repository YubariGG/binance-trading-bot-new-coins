#!/usr/bin/python3
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
        self.sleep = [1 + i*0.05 for i in range(1, 11)]

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
            try:
                # API call:
                self.current_coins = self.client.get_all_tickers() 
                time.sleep(sleep)
            except:
                self.email.send(f"<p>Current pool evaluation failed due to the following reason:</p><p>{e}</p>", "ERROR")

    def check_current_pool(self):
        time.sleep(1) # To avoid faster execution than check new coins
        while True:
            initial_coins = copy.deepcopy(self.coins)
            for initial_coin in initial_coins.keys():
                located_coin = list(filter(lambda coin: coin["symbol"] == initial_coin, self.current_coins))
                if len(located_coin) > 1:
                    del self.coins[initial_coin]

    def update_status(self):
        self.email_sent = False
        while True:
            if (current_time := datetime.fromtimestamp(time.time()).strftime("%H:%M")) == "00:01": self.email_sent = False
            if current_time == "00:00" and not self.email_sent:
                text = f"<p>Current pool length is {len(self.coins)}. Next update tomorrow at 00:00 current time.</p>"
                self.email.send(text, "Current status")
                self.email_sent = True

    def order_email(self, order, coin, text):
        if text == "BUY":
            body = f"""
                        <ul>
                        <li>
                            <strong>{coin}</strong>: bought {float(order['cummulativeQuoteQty']):.3f} USDT at a price of <strong>{order['price']}</strong> USDT. Including the commision fee we have a volume of <strong>{order['vol2trade']}</strong> {coin} to trade with.
                        </li>
                        </ul>
                    """
            self.email.send(body, "Buy order placed")
        else:
            body = f"""
                        <ul>
                        <li>
                           <strong>{coin}</strong>: sold <strong>{float(order['realQuote']):.3f}</strong> {coin} at a price of {order['price']} USDT. A margin of {float(order['margin']):.3f} USDT was made with the current transaction. 
                        </li>
                        </ul>
                    """
            self.email.send(body, "Sell order placed")

    def main_aggressive(self):        
        # Scanner daemon configuration:
        for sleep in self.sleep:
            threading.Thread(target=self.check_new_coins, args=(sleep,), daemon=True).start()

        # Process to remove no longer existing coins:
        threading.Thread(target=self.check_current_pool, args=[], daemon=True).start()

        # Daemon to update our status
        threading.Thread(target=self.update_status, args=[], daemon=True).start()

        # Main logic of the trading algorithm
        self.email.send("<p>Started the service using systemctl</p>","Startup")
        while True:
            try:
                # Buying logic:
                if len(self.current_coins) > len(self.coins):
                    current_coin_pool = copy.deepcopy(self.current_coins)
                    for coin in current_coin_pool:
                        # New coin detected:
                        if coin["symbol"] not in self.coins and self.pairing in coin["symbol"]:
                            order = self.order_handler.buy(coin["symbol"], float(coin["price"]))
                            threading.Thread(target=self.order_email, args=[order[coin["symbol"]], coin["symbol"], "BUY"]).start()
                            time.sleep(0.2)
                            sell_order = self.order_handler.sell(order[coin["symbol"]])
                            threading.Thread(target=self.order_email, args=[sell_order[coin["symbol"]], coin["symbol"], "SELL"]).start()
                            self.coins[coin["symbol"]] = True

            except Exception as e:
                self.email.send(f"<p>Main routine failed due to the following reasons:</p><p>{e}</p>", "ERROR")
                break


if __name__ == "__main__":
    binance = BinanceHandler()
    binance.main_aggressive()
