import boto3
import os
import json
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

def dynamo_table():
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(os.environ['DYNAMODB_TABLE'])

table = dynamo_table()

def get_connections():
    record = get_item('connections', 0)
    if record:
        return record["connections"], int(record["version"])
    return [], 0

def store_connection_row(connection_id):
    debug("START store the connection")
    connections, version = get_connections()
    connections.append(connection_id)
    update_item('connections', 0, {'connections': connections, 'version': str(version + 1)})
    print("END connection stored")

def delete_connection(connection_id):
    debug("START delete the connection")
    connections, version = get_connections()
    if len(connections) > 0:
        debug("found connections: ", connections)
        connections.remove(connection_id)

        update_item('connections', 0, {'connections': connections, 'version': str(version + 1)})
        print("END connection deleted")


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

def notify_users(event, message):
    connections, _ = get_connections()
    if len(connections) > 0:
        for connection_id in connections:
            send_to_connection(event, message, connection_id)


def get_item(partition_id, sort_id):
    response = table.get_item(
        Key={
            'partition_id': partition_id,
            'sort_id': sort_id
        },
        ConsistentRead=True
    )
    return response.get("Item", None)

def query_for_max_bid(item_id):
    response = table.query(
        KeyConditionExpression=Key('partition_id').eq(item_id),
        ScanIndexForward=False,
        Limit=1
    )
    return response

def get_all_bids():
    debug("START - get all bids")
    inventory = get_item('inventory', 0)
    debug("found items: ", inventory)
    listings = []
    if inventory:
        for item in inventory["items"]: 
            debug("looking for latest bid for ", item)  
            response = query_for_max_bid(item)
            listing = next(iter(response['Items']), None)         
            debug("found individual item: ", listing)
            listings.append(parse_listing(listing))

    debug("DONE getting bids, found: ", listings)
    return listings

def parse_listing(listing):
    if listing:
        current_bid = listing.get('sort_id', None)
        if current_bid:
            # convert it to a nicely readable dollar format
            current_bid = str((current_bid / 100).quantize(Decimal("0.00")))
        return { 
            'title': listing.get('partition_id', None),
            'current_bid': current_bid,
            'timestamp': listing.get('bid_at', None)
        }
    return None

def debug(*args):
    print(*args)


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

# def delete_item(partition_id, sort_id):
#     table.delete_item(
#         Key={
#             'partition_id': partition_id,
#             'sort_id': sort_id
#         }
#     )




def handle_error(message, event, error_code=400):
    print("Error: ", message)
    send_to_connection(event, message)
    return {
        "statusCode": error_code
    }

