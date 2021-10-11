#!/bin/sh
if [ ! $(pgrep -f main.py) ]; then
    cd /home/ubuntu./updated bot
    /usr/bin/python3 main.py

fi