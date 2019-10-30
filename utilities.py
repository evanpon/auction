import boto3
import os
import json
from boto3.dynamodb.conditions import Key

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
        delete_all_rows_for_connection(event, connection_id)


def get_item(partition_id, connection_id):
    response = table.get_item(
        Key={
            'partition_id': partition_id,
            'connection_id': connection_id
        }
    )
    return response.get("Item", None)

def get_room_row(room, connection_id):
    return get_item(room, connection_id)

def get_connection_row(connection_id):
    return get_item(partition_id_from_connection(connection_id), connection_id)

def store_item(partition_id, connection_id, attributes=None):
    ''' Stores the provided attributes in Dynamo. If none are provided, it just stores the 
        composite key.'''
    if attributes is None:
        attributes = {}
    key = {'partition_id': partition_id, 'connection_id': connection_id}
    item = {**key, **attributes}
    return table.put_item(
        Item=item
    )

def store_connection_row(connection_id, attributes):
    return store_item(partition_id_from_connection(connection_id), connection_id, attributes)

def store_room_row(room, connection_id, attributes):
    return store_item(room, connection_id, attributes)

def update_item(partition_id, connection_id, attributes):
    update_expressions = []
    expression_values = {}
    for key in attributes:
        update_expressions.append(f"SET {key}=:{key}")
        expression_values[f":{key}"] = attributes[key]

    update_expression_str = ','.join(update_expressions)

    return table.update_item(
        Key={
            'partition_id': partition_id,
            'connection_id': connection_id
        },
        UpdateExpression=update_expression_str,
        ExpressionAttributeValues=expression_values
    )
def delete_item(partition_id, connection_id):
    table.delete_item(
        Key={
            'partition_id': partition_id,
            'connection_id': connection_id
        }
    )
def delete_all_rows_for_connection(event, connection_id):
    user = get_connection_row(connection_id)
    if user:
        room = user["room"]
        delete_item(room, connection_id)
        delete_item(partition_id_from_connection(connection_id), connection_id)

        users = get_room_members(room)
        message = f'{user["user"]} has left {room}'
        notify_users(event, users, message)
        finish_voting_if_complete(event, room, users)

def notify_users(event, users, message):
    for user in users:
        connection_id = user['connection_id']
        send_to_connection(event, message, connection_id)

def notify_room(event, room, message):
    users = get_room_members(room)
    notify_users(event, users, message)

def get_room_members(room):
    response = table.query(
        KeyConditionExpression=Key('partition_id').eq(room)
    )
    return response['Items']


# Here we are using the connection_id as the partition_key, so we can 
# find this row on disconnect. Prefix it with a reserved character (the asterisk)
# to make sure it doesn't overlap with any real room names.
def partition_id_from_connection(connection_id):
    return f'*{connection_id}'

def handle_error(message, event, error_code=400):
    print("Error: ", message)
    send_to_connection(event, message)
    return {
        "statusCode": error_code
    }

def finish_voting_if_complete(event, room, users, completed_votes=None):
    if completed_votes is None:
        completed_votes = []
        for user in users:
            vote = user.get("vote", None)
            if vote is not None:
                completed_votes.append({"user": user["user"], "vote": int(vote)})
    if len(users) == len(completed_votes):
        for user in users:
            connection_id = user['connection_id']
            update_item(room, connection_id, {"vote": None})
            send_to_connection(event, completed_votes, connection_id)

