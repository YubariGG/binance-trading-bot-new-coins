import json
from binance_client import Binance

# Classes:
binance_client = Binance()


def run(event, context):
    # Main logic:
    binance_client.update_data()
    changing_coins = binance_client.read_changes()
    new_coins = binance_client.read_new_coins()

    # Build api body:
    body = {
        "Message": "Current state",
        "Existing relevant coins": changing_coins,
        "New coins": new_coins
    }

    return {"statusCode": 200, "body": json.dumps(body)}
