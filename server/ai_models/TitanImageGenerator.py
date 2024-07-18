from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError 
from utils.error_check import handle_boto3_error
from inspect import currentframe, getframeinfo
from aws_utils import generate_presigned_url
from botocore.client import Config
from fastapi import HTTPException
from datetime import datetime
from random import random
from PIL import Image
import traceback
import botocore
import asyncio
import logging
import base64
import boto3
import json
import uuid
import os
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TitanImageGenerator:
	async def generate_single_image(self, idx, prompt):
		start = datetime.now()
		try:
			print('Ready to Gen : ', idx, prompt)
			bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1', aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))
			accept = "application/json"
			content_type = "application/json"
			num = int(random() * 10000)
			body = {
				"taskType": "TEXT_IMAGE",
				"textToImageParams": {
					"text": prompt
				},
				"imageGenerationConfig": {
					"numberOfImages": 1,
					"height": 512,
					"width": 512,
					"cfgScale": 8.0,
					"seed": num
				}
			}
			json_body = json.dumps(body)
			byte_body = json_body.encode('utf-8')
			loop = asyncio.get_event_loop()
			response = await loop.run_in_executor(None, self.invoke_model_with_args,bedrock, byte_body, accept, content_type)
			response_body = json.loads(response.get("body").read())
			base64_image = response_body.get("images")[0]            
			base64_bytes = base64_image.encode('ascii')
			image_bytes = base64.b64decode(base64_bytes)
			duration = datetime.now() - start
			img_id = str(uuid.uuid4())
			img_url = self.processAndSaveImage(base64.b64encode(image_bytes).decode('utf-8'), img_id, "browse-image-v2")
			return idx, img_id, prompt, img_url, 'titan'
		except ClientError as e:
			duration = datetime.now() - start
			return handle_boto3_error(e)
		except BotoCoreError as e:
			duration = datetime.now() - start
			raise HTTPException(status_code=500, detail={'message':f"AWS Botocore Error: {str(e)}",'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})
		except Exception as e:
			duration = datetime.now() - start
			raise HTTPException(status_code=500, detail={'message':f"generate with bedrock error{str(e)}",'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})
		
	def invoke_model_with_args(self, bedrock, byte_body, accept, content_type):
		return bedrock.invoke_model(
			body=byte_body,
			modelId="amazon.titan-image-generator-v1",
			accept=accept,
			contentType=content_type
		)

	def processAndSaveImage(self, image_data: str, img_id: str, s3_bucket_name: str):
		try:
			image_bytes = base64.b64decode(image_data)
			image = Image.open(io.BytesIO(image_bytes))

			buffered = io.BytesIO()
			image.save(buffered, format="JPEG", quality=85)
			compressed_image_bytes = buffered.getvalue()
			s3_client = boto3.client(
				"s3", region_name="us-east-2", config=Config(signature_version="s3v4")
			)

			image_key = f"{img_id}.jpg"
			s3_client.upload_fileobj(
				io.BytesIO(compressed_image_bytes),
				s3_bucket_name,
				image_key,
				ExtraArgs={
	                "ACL": "public-read",
	                "ContentType": "image/jpeg",
	                "ContentDisposition": "inline",
	            },
			)

			url = generate_presigned_url(img_id, s3_bucket_name)
			return url
		except NoCredentialsError:
			logger.error("No AWS credentials found")
			raise HTTPException(
				status_code=500,
				detail={
					"message": "Missing Credentials",
					"currentFrame": getframeinfo(currentframe()),
				},
			)
		except Exception as error:
			logger.error(f"Error in processAndSaveImage: {error}")
			raise HTTPException(
				status_code=500,
				detail={
					"message": "Internal Server Error",
					"currentFrame": getframeinfo(currentframe()),
					"detail": str(traceback.format_exc()),
				},
			)