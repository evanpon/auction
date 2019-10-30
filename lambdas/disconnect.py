from utilities import delete_all_rows_for_connection

def execute(event, context):
    connection_id = event["requestContext"]["connectionId"]
    delete_all_rows_for_connection(event, connection_id)
    return {
        "statusCode": 200
    }
