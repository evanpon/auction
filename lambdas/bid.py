from utilities import (store_bid, notify_users)
import json
import datetime

def execute(event, context):

    body = json.loads(event["body"])
    item_id = body["item_id"]
    bid_amount = body["bid_amount"]
    attributes = {
        "contact_info": body["contact_info"],
        "timestamp": datetime.datetime.now().ctime()
    }     
    store_bid(item_id, bid_amount, attributes)

    notify_users(event, {"item_id": item_id, "bid_amount": bid_amount})
    return {
        "statusCode": 200
    }
