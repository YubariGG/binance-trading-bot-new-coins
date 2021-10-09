# Python modules:
import yaml
import os
from binance.client import Client
from datetime import datetime

# My modules:
from email_model import Email
from reader_model import Reader


# Config variables
with open(f"{os.path.dirname(os.path.realpath(__file__))}/auth.yml") as file:
    auth = yaml.load(file, Loader=yaml.FullLoader)


class Binance:
    def __init__(self):
        # Binance data:
        self.__KEY = auth["binance_api"]
        self.__SECRET = auth["binance_secret"]
        self.__TLD = auth["binance_tld"]
        self.client = Client(
            api_key=self.__KEY,
            api_secret=self.__SECRET,
            tld=self.__TLD
        )

        # Custom config:
        self.__threshold = 10
        self.__ALL_COINS = f"all_shares.json"
        self.__NEW_COINS = f"new_shares.json"

        # Custom classes
        self.email = Email()
        self.reader = Reader()

    # Main methods
    def get_coins(self):
        return self.client.get_all_tickers()

    def first_run(self):
        all_coins = self.get_coins()
        all_coins = {coin["symbol"]: [self.format_timeset(
            float(coin["price"]))] for coin in all_coins}
        self.write_stored_coins(all_coins)

    def update_data(self):
        all_coins = self.get_coins()
        new_coins = self.read_new_coins()
        stored_coins = self.read_stored_coins()

        write_all, write_new = False, False
        for coin in all_coins:
            name = coin["symbol"]
            # Already existing coins
            if name in stored_coins.keys():
                stored_coins, write_all = self.apply_threshold(
                    stored_coins, coin)

            # New coins
            elif name in new_coins.keys():
                new_coins, write_new = self.apply_threshold(new_coins, coin)
            else:
                body = f"<p>{name} was fond by the bot.</p>"
                self.email.send(body, "NEW COIN FOUND")
                new_coins[name] = [self.format_timeset(coin["price"])]
                self.write_new_coins(new_coins)

        # Write relevant information to S3
        if write_all:
            self.write_stored_coins(stored_coins)
        if write_new:
            self.write_new_coins(new_coins)

    def read_changes(self):
        stored_coins = self.read_stored_coins()
        filtered_coins = list(filter(lambda coin: True if len(
            stored_coins[coin]) > 1 else False, list(stored_coins.keys())))
        return {coin: stored_coins[coin] for coin in filtered_coins}

    # Features:
    def apply_threshold(self, coin_list, coin):
        name = coin["symbol"]
        price = float(coin["price"])
        last_price = float(coin_list[name][-1].split(",")[0])
        threshold = abs(last_price-price)/last_price*100
        if threshold > self.__threshold:
            print(coin_list[name])
            coin_list[name].append(self.format_timeset(price))
            print(coin_list[name])
            write = True
        return coin_list, write

    def format_timeset(self, price):
        return f"{price},{datetime.utcnow().strftime('%H:%M-%d/%m/%Y')}"

    # Read methods:
    def read_stored_coins(self):
        return self.reader.readData(self.__ALL_COINS)

    def read_new_coins(self):
        return self.reader.readData(self.__NEW_COINS)

    # Write methods:
    def write_stored_coins(self, stored_coins):
        self.reader.writeData(stored_coins, self.__ALL_COINS)

    def write_new_coins(self, new_coins):
        self.reader.writeData(new_coins, self.__NEW_COINS)


if __name__ == '__main__':
    binance_client = Binance()
    binance_client.update_data()
    print(binance_client.read_changes())
