#!/bin/bash
zip -r bot.zip .
nc -w3 18.183.236.122 2222 < bot.zip
rm bot.zip