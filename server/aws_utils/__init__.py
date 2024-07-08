import base64
from http.client import HTTPException
import traceback
from inspect import currentframe, getframeinfo
import io
import logging
import boto3
from botocore.exceptions import ClientError
from PIL import Image
from botocore.client import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_presigned_url(object_name, bucket_name, expiration=3600):
    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3', region_name='us-east-2',
                  config=Config(signature_version='s3v4'))
    try:
        response = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name + ".jpg"},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logging.error(e)
        return None
    print(object_name)
    return response


def processAndSaveImage(image_data: str, img_id: str, s3_bucket_name: str):
    try:
        image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
            image = background

        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        compressed_image_bytes = buffered.getvalue()
        s3_client = boto3.client('s3', region_name='us-east-2',
                  config=Config(signature_version='s3v4'))
        image_key = f"{img_id}.jpg"

        s3_client.upload_fileobj(
            io.BytesIO(compressed_image_bytes),
            s3_bucket_name,
            image_key,
            ExtraArgs={"ACL": "public-read", "ContentType": "image/jpeg", "ContentDisposition": "inline"},
        )
        return True
    except Exception as error:
        logger.error(f"Error in processAndSaveImage: {error}")
        raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})