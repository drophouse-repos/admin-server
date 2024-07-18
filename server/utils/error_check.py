import traceback
from inspect import currentframe, getframeinfo
from fastapi import HTTPException  # , Request
import openai
import botocore.exceptions
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def handle_openai_error(error):
    if isinstance(error, openai.BadRequestError):
        raise HTTPException(status_code=400, detail={'message':"Prompt Violates Our Content Policy", 'currentFrame': getframeinfo(currentframe())})
    elif isinstance(error, openai.AuthenticationError):
        raise HTTPException(status_code=401, detail={'message':"Authentication Error: " + error.message, 'currentFrame': getframeinfo(currentframe())})
    elif isinstance(error, openai.RateLimitError):
        raise HTTPException(status_code=429, detail={'message':"Rate Limit Exceeded: " + error.message, 'currentFrame': getframeinfo(currentframe())})
    else:
        raise HTTPException(status_code=500, detail={'message':"OpenAI Error: " + error.message, 'currentFrame': getframeinfo(currentframe())})

def handle_boto3_error(error):
    if isinstance(error, botocore.exceptions.ClientError):
        error_code = error.response['Error']['Code']
        if error_code == "ValidationException":
            raise HTTPException(status_code=400, detail={'message':"Prompt Violates Our Content Policy", 'currentFrame': getframeinfo(currentframe())})
        elif error_code == "LimitExceededException ":
            raise HTTPException(status_code=429, detail={'message':f"Bedrock Ratelimit Exceeded: {str(error)}", 'currentFrame': getframeinfo(currentframe())})
        else:
            error_message = error.response['Error']['Message']
            raise HTTPException(status_code=500, detail={'message':f"Bedrock Error occurred: {error_code} - {error_message}", 'currentFrame': getframeinfo(currentframe())})
    else:
        raise HTTPException(status_code=500, detail={'message':f"Bedrock Error: {str(error)}", 'currentFrame': getframeinfo(currentframe())})    

def checkUnprocessibleEntity(err):
    if err.status_code == 422:
        details = err.detail
        logger.error(f"HTTPException 422 occurred: {details}")
        raise HTTPException(status_code=422, detail={'message':"Unprocessable Entity", 'currentFrame': getframeinfo(currentframe())})