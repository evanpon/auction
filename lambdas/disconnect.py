from utilities import delete_connection

def execute(event, context):
    connection_id = event["requestContext"]["connectionId"]
    delete_connection(connection_id)
    return {
        "statusCode": 200
    }
