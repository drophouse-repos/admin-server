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

class MockTitanImageGenerator:
    async def generate_single_image(self, idx, prompt):
        try:
            if random() < 0.1:  # Simpulate random failure ~10% chance to raise an HTTPException
                raise HTTPException(status_code=500, detail="Mocked HTTPException for testing")

            img_id = str(uuid.uuid4())
            img_url = self.processAndSaveImage(self.get_mock_image(), img_id, "browse-image-v2") # change mock bucket if need
            return idx, img_id, prompt, 'mocked-titan'
        except Exception as e:
            raise HTTPException(status_code=500, detail={
                'message': f"Mock generate with error: {str(e)}",
                'currentFrame': getframeinfo(currentframe()),
                'detail': str(traceback.format_exc())
            })
    
    def get_mock_image(self):
        local_image_path = './images/mock_image.png'
        if os.path.exists(local_image_path):
            with open(local_image_path, 'rb') as image_file:
                image_bytes = image_file.read()
        else:
            image = Image.new('RGB', (512, 512), color=(int(random() * 255), int(random() * 255), int(random() * 255)))
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            image_bytes = buffered.getvalue()
        
        return base64.b64encode(image_bytes).decode('utf-8')

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

            return img_id
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