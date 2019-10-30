import boto3
import os
import json
from boto3.dynamodb.conditions import Key, Attr

def dynamo_table():
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(os.environ['DYNAMODB_TABLE'])

table = dynamo_table()

def send_to_connection(event, message, connection_id=None):
    if not isinstance(message, str):
        message = json.dumps(message)
    print
    if connection_id is None:
        connection_id = event["requestContext"]["connectionId"]

    endpoint_url = "https://" + event["requestContext"]["domainName"] + "/" + event["requestContext"]["stage"]
    gatewayapi = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
    try:
        gatewayapi.post_to_connection(Data=message,ConnectionId=connection_id)
    except Exception as error:
        print("Error sending to connection:", error)
        delete_connection(connection_id)


def get_item(partition_id, sort_id):
    response = table.get_item(
        Key={
            'partition_id': partition_id,
            'sort_id': sort_id
        },
        ConsistentRead=True
    )
    return response.get("Item", None)

def get_all_bids():
    # TODO - doesn't actually work, just pseudocode
    items = get_item('items', 'items')
    responses = []
    for item in items:            
        response = table.query(
            KeyConditionExpression=Key('partition_id').eq(item["item_id"])
        )
        responses << response

    return responses


def get_connected_users():
    return get_item('connections', 'connections')

def get_items():
    return get_item('items', 'items')

def store_item(partition_id, sort_id, attributes=None):
    ''' Stores the provided attributes in Dynamo. If none are provided, it just stores the 
        composite key.'''
    if attributes is None:
        attributes = {}
    key = {'partition_id': partition_id, 'sort_id': sort_id}
    item = {**key, **attributes}
    return table.put_item(
        Item=item
    )

def store_connection_row(connection_id):
    print("START store the connection")
    record = get_item('connections', 'connections')

    print("connections:", record)
    connections = []
    version = 0
    if record:
        print("found record: ", record)
        connections = record["connections"] 
        version = int(record["version"])

    
    connections.append(connection_id)
    update_item('connections', 'connections', {'connections': connections, 'version': str(version + 1)})
    print("END connection stored")

def store_bid(item_id, bid_amount, attributes):
    return store_item(item_id, bid_amount, attributes)

def update_item(partition_id, sort_id, attributes):
    update_expressions = []
    expression_values = {}
    for key in attributes:
        update_expressions.append(f"{key}=:{key}")
        expression_values[f":{key}"] = attributes[key]

    update_expression_str = "SET " + ','.join(update_expressions)
    version = str(int(attributes['version']) - 1)
    print("Version:", version)
    print("update expression: ", update_expression_str)
    print('attribute values:', expression_values)
    return table.update_item(
        Key={
            'partition_id': partition_id,
            'sort_id': sort_id
        },
        UpdateExpression=update_expression_str,
        ExpressionAttributeValues=expression_values,
        ConditionExpression=Attr('version').not_exists() | Attr('version').eq(version)
    )

def delete_item(partition_id, sort_id):
    table.delete_item(
        Key={
            'partition_id': partition_id,
            'sort_id': sort_id
        }
    )

def delete_connection(connection_id):
    print("START delete the connection")
    record = get_item('connections', 'connections')

    if record:
        print("found connections record: ", record)
        connections = record["connections"]
        connections.remove(connection_id)
        version = int(record["version"])   

        update_item('connections', 'connections', {'connections': connections, 'version': str(version + 1)})
        print("END connection deleted")


def notify_users(event, message):
    # TODO: must modify
    users = get_item('connection', 'connection')
    for user in users:
        connection_id = user['connection_id']
        send_to_connection(event, message, connection_id)


def handle_error(message, event, error_code=400):
    print("Error: ", message)
    send_to_connection(event, message)
    return {
        "statusCode": error_code
    }

