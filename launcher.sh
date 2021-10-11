#!/bin/sh
if [ ! $(pgrep -f main.py) ]; then
    cd /home/ubuntu/binance-trading-bot-new-coins
    /usr/bin/python3 main.py

fi