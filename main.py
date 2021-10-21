from trade_client import *
from store_order import *
from load_config import *

from collections import defaultdict
from datetime import datetime, time
import time
import threading
import json
import os.path
import models

# loads local configuration
config = load_config('config.yml')
email = models.Email()


def get_all_coins():
    """
    Returns all coins from Binance
    """
    return client.get_all_tickers()


def generate_coin_seen_dict(all_coins):
    """
    This method should be used once before starting the loop.
    The value for every coin detected before the loop is set to True in the coin_seen_dict.
    All the new coins detected during the loop will have a value of False.
    """
    coin_seen_dict = defaultdict(bool)
    for old_coin in all_coins:
        coin_seen_dict[old_coin['symbol']] = True
    return coin_seen_dict


def get_new_coins(coin_seen_dict, all_coins_recheck):
    """
    This method checks if there are new coins listed and returns them in a list.
    The value of the new coins in coin_seen_dict will be set to True to make them not get detected again.
    """
    result = []

    for new_coin in all_coins_recheck:
        if not coin_seen_dict[new_coin['symbol']]:
            result += [new_coin]

            # this line ensures the new coin isn't detected again
            coin_seen_dict[new_coin['symbol']] = True

    return result


def get_price(coin, pairing):
    """
    Get the latest price for a coin
    """
    return client.get_ticker(symbol=coin+pairing)['lastPrice']


def add_updated_all_coins_to_queue(queue):
    """
    This method makes a request to get all coins and adds it to the given queue.
    """
    all_coins_updated = get_all_coins()
    queue += [all_coins_updated]


def make_threads_to_request_all_coins(queue, interval=0.1, max_amount_of_threads=20, max_queue_length=20):
    """
    This method creates threads for new requests to get all coins.
    A new thread is created every interval.
    If there are more threads than max_amount_of_threads no new threads will be created, after every 1 second there
    will be a new attempt to create a thread.
    The amount of threads can increase if the response from Binance to get all coins increases.
    If the queue length gets bigger than max_queue_length no new threads will be created, after every 1 second there
    will be a new attempt to create a thread.
    The amount of elements in the queue can increase if the while loop in main takes long to handle.
    """
    while True:
        time.sleep(interval)
        # checks if the amount of threads is bigger than max_amount_of_threads
        if len(threading.enumerate()) > max_amount_of_threads:
            # print("Too many threads, waiting 1 second to attempt to create a new thread.")
            time.sleep(1)
        # checks if the queue isn't getting too big
        elif len(queue) > max_queue_length:
            # print(
            #     "Queue length too big, waiting 1 second to attempt to create a new thread.")
            time.sleep(1)
        else:
            threading.Thread(
                target=add_updated_all_coins_to_queue, args=(queue,)).start()


def main():
    """
    Sells, adjusts TP and SL according to trailing values
    and buys new coins
    """
    # store config deets
    tp = config['TRADE_OPTIONS']['TP']
    sl = config['TRADE_OPTIONS']['SL']
    enable_tsl = config['TRADE_OPTIONS']['ENABLE_TSL']
    tsl = config['TRADE_OPTIONS']['TSL']
    ttp = config['TRADE_OPTIONS']['TTP']
    pairing = config['TRADE_OPTIONS']['PAIRING']
    qty = config['TRADE_OPTIONS']['QUANTITY']
    frequency = config['TRADE_OPTIONS']['RUN_EVERY']
    test_mode = config['TRADE_OPTIONS']['TEST']

    all_coins = get_all_coins()
    coin_seen_dict = generate_coin_seen_dict(all_coins)

    # Poner este bloque de debajo sirve para ver si la API está devolviendo correctamente los mismos valores que la aplicación.
    # Los valores que devuelve la aplicación se pueden ver en esta página filtrando por Fiat--> USDT
    # https://www.binance.com/es/markets

    # arrayComprobacionBinance = []
    # for i in coin_seen_dict :
    #     if i[-4:] == 'USDT'  :
    #         print(i)
    #         arrayComprobacionBinance.append(i)

    # this list will work as a queue, if a new updated all_coins is received it will be added to this queue hola

    queue_of_updated_all_coins = []
    # start a thread to run the make_threads_to_request_all_coins method
    threading.Thread(target=make_threads_to_request_all_coins,
                     args=(queue_of_updated_all_coins,)).start()
    # this is just used to calculate the amount of time between getting updated all_coins
    t0 = time.time()
    while True:
        try:

            # check if the order file exists and load the current orders
            # basically the sell block and update TP and SL logic
            if os.path.isfile('order.json'):
                order = load_order('order.json')

                for coin in list(order):

                    volume = float(order[coin]['executedQty']) ## CAMBIAR POR executedQty?--> executedQty ES LO QUE REALMENTE SE HA COMPRADO.
                    # store some necesarry trade info for a sell
                    stored_price = float(order[coin]['cummulativeQuoteQty']) / volume ## 
                    coin_tp = order[coin]['tp']
                    # coin_sl = order[coin]['sl'] No se utiliza para nada
                    symbol = coin.split(pairing)[0] ## pairing es por config

                    last_price = get_price(symbol, pairing)

                    # Conditions:
                    update_tp = float(
                        last_price) > stored_price + (stored_price*coin_tp / 100)
                    sell_sl = float(last_price) < stored_price - \
                        (stored_price*sl / 100)
                    sell_tp = float(last_price) > stored_price + \
                        (stored_price*tp / 100)

                    # update stop loss and take profit values if threshold is reached
                    if update_tp and enable_tsl:
                        # increase as absolute value for TP
                        new_tp = float(last_price) + \
                            (float(last_price)*ttp / 100)
                        # convert back into % difference from when the coin was bought
                        new_tp = float(
                            (new_tp - stored_price) / stored_price*100)

                        # same deal as above, only applied to trailing SL
                        new_sl = float(last_price) - \
                            (float(last_price)*tsl / 100)
                        new_sl = float(
                            (new_sl - stored_price) / stored_price*100)

                        # new values to be added to the json file
                        order[coin]['tp'] = new_tp
                        order[coin]['sl'] = new_sl
                        store_order('order.json', order)

                        # print(
                        #     f'updated tp: {round(new_tp, 3)} and sl: {round(new_sl, 3)}')

                    # close trade if tsl is reached or trail option is not enabled
                    elif sell_sl or (sell_tp and not enable_tsl):
                        try:
                            # Save the selling trades:
                            if os.path.isfile('sold.json'):
                                sold_coins = load_order('sold.json')

                            else:
                                sold_coins = {}

                            # sell for real if test mode is set to false
                            if not test_mode:
                                sell = create_order(
                                    coin, volume, 'SELL')
                                margin = (
                                    float(last_price) - stored_price) / float(stored_price)*100
                                sold_coins[coin] = sell
                                store_order('sold.json', sold_coins)

                                # Notificar por email
                                body = f"<p>Se ha vendido {volume} de {coin} a un precio de {last_price} con un margen del {margin}</p>"
                                email.send(body, "NUEVA VENTA EJECUTADA")

                            else:
                                sold_coins[coin] = {
                                    'symbol': coin,
                                    'price': last_price,
                                    'volume': volume,
                                    'time': datetime.timestamp(datetime.now()),
                                    'profit': float(last_price) - stored_price,
                                    'relative_profit': round((float(last_price) - stored_price) / stored_price*100, 3)
                                }

                                store_order('sold.json', sold_coins)

                            # remove order from json file
                            order.pop(coin)
                            store_order('order.json', order)

                        except Exception as e:
                            # print(e)
                            body = f"<p>Se ha producido un error en el bloque de ventas <br> {e} .</p>"
                            email.send(body, "ERROR EN EL CODIGO")

            else:
                order = {}

            # check if a new all_coins_updated is on the queue
            if len(queue_of_updated_all_coins) > 0:
                # get the first updated coins from the queue
                all_coins_updated = queue_of_updated_all_coins.pop(0)
                # check if new coins are listed
                new_coins = get_new_coins(coin_seen_dict, all_coins_updated)

                # print("time to get updated list of coins: ", time.time() - t0)
                # print("current amount of threads: ",
                #       len(threading.enumerate()))
                # print("current queue length: ", len(
                #     queue_of_updated_all_coins))
                t0 = time.time()
            else:
                # if no new all_coins_updated is on the queue, new_coins should be empty
                new_coins = []

            # the buy block and logic pass
            if len(new_coins) > 0:

                ## Avisar por email de que se han descubierto nuevas monedas
                body = f'<p>New coins detected: {new_coins} . </p>'
                email.send(body, "NUEVAS MONEDAS DETECTADAS")

                for coin in new_coins:

                    # buy if the coin hasn't already been bought
                    if coin['symbol'] not in order and pairing in coin['symbol']:
                        symbol_only = coin['symbol'].split(pairing)[0]
                        # print(f"Preparing to buy {coin['symbol']}")

                        price = get_price(symbol_only, pairing)
                        volume = convert_volume(coin['symbol'], qty, price)

                        try:
                            # Run a test trade if true
                            if config['TRADE_OPTIONS']['TEST']:
                                order[coin['symbol']] = {
                                    'symbol': symbol_only+pairing,
                                    'price': price,
                                    'volume': volume,
                                    'time': datetime.timestamp(datetime.now()),
                                    'tp': tp,
                                    'sl': sl
                                }

                                # print('PLACING TEST ORDER')

                            # place a live order if False
                            else:
                                order[coin['symbol']] = create_order(
                                    symbol_only+pairing, volume, 'BUY')
                                order[coin['symbol']]['tp'] = tp
                                order[coin['symbol']]['sl'] = sl

                                # print(
                                #     f"Order created with {volume} on {coin['symbol']}")

                                store_order('order.json', order)

                                # Notificar por email
                                # if not isTrading :
                                body = f"<p>Se han comprado {volume} de {symbol_only} {pairing} a un precio de {price}.</p>"
                                email.send(body, "NUEVA COMPRA EJECUTADA")

                        except Exception as e:
                            # print(e)
                            body = f"<p>Se ha producido una excepción en el bloque de compras <br> {e}.</p>"
                            email.send(body, "ERROR EN EL CÓDIGO")

                    else:
                        # print(
                        #     f"New coin detected, but {coin['symbol']} is currently in portfolio, or {pairing} does not match")
                        body = f"<p>New coin detected, but {coin['symbol']} is currently in portfolio, or {pairing} does not match</p>"
                        email.send(body, "NEW COIN DETECTED but not bought")

            else:
                pass

        except Exception as e:
            body = f"<p>No se ha ejecutado el bucle principal{e}</p>"
            email.send(body,
                       "ERROR EN EL CÓDIGO")


if __name__ == '__main__':
    print('working...')
    main()