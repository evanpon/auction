from utilities import (get_all_bids, send_to_connection)

def execute(event, context):
    data = get_all_bids()
    send_to_connection(event, data)
    return {
        "statusCode": 200
    }
