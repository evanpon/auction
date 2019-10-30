
# Doesn't really do anything, since we can't send data back to the user until after this 
# function completes (the connection is not established until then, and serverless currently
# doesn't support returning data through to API Gateway - see https://github.com/serverless/serverless/issues/6130)
def execute(event, context):
    return {
        "statusCode": 200
    }
