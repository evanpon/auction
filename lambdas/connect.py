from utilities import (store_connection_row)

def execute(event, context):
    connection_id = event["requestContext"]["connectionId"]
    store_connection_row(connection_id)
    return {
        "statusCode": 200
    }
