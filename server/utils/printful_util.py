from botocore.exceptions import NoCredentialsError
from inspect import currentframe, getframeinfo
from aws_utils import generate_presigned_url
from botocore.client import Config
from fastapi import HTTPException
from io import BytesIO
from PIL import Image
import numpy as np
import traceback
import requests
import logging
import base64
import boto3
import uuid
import cv2
import os
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.printful.com"
PRIVATE_TOKEN = os.environ.get("PRINTFUL_PRIVATE_TOKEN")

process_folder = "../pre_processing_printful_images/"
if not os.path.exists(process_folder):
    os.makedirs(process_folder)


def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read())
        return encoded_string.decode("utf-8")


def applyMask_and_removeBackground(input_image_url, mask_path, img_id):
    try:
        shape_image = Image.open(mask_path).convert("RGBA")
        
        unique_id = uuid.uuid4()
        image_path = os.path.join(process_folder, f'{unique_id}.png')
        
        if 'data:image' in input_image_url:
            input_image_url = input_image_url.split(",")[1]
            jpeg_data = base64.b64decode(input_image_url)
            background_image = Image.open(BytesIO(jpeg_data)).resize((512, 512)).convert("RGBA")
        else:
            response = requests.get(input_image_url)
            background_image = Image.open(BytesIO(response.content)).resize((512, 512)).convert("RGBA")
        
        if not background_image:
            raise Exception("Image not found")
        
        # Composite the images
        r, g, b, a = shape_image.split()
        composite_image = Image.composite(shape_image, background_image, a)
        composite_image.save(image_path)

        # Remove green background using a color range filter
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        os.remove(image_path)
        
        # Convert image to BGR (cv2 works with BGR format)
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
        
        # Define the green screen color range
        # lower_green = np.array([0, 100, 0, 255], dtype=np.uint8)
        # upper_green = np.array([120, 255, 120, 255], dtype=np.uint8)
        # lower_green = np.array([81, 177, 37, 255], dtype=np.uint8)
        # upper_green = np.array([83, 179, 39, 255], dtype=np.uint8)
        lower_green = np.array([82, 178, 38, 255], dtype=np.uint8)
        upper_green = np.array([82, 178, 38, 255], dtype=np.uint8)
        
        # Create a mask to remove the green background
        mask = cv2.inRange(image_bgr, lower_green, upper_green)

        # Apply morphological operations to clean up the mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        mask_inv = cv2.bitwise_not(mask)
        
        # Extract the foreground
        foreground = cv2.bitwise_and(image, image, mask=mask_inv)
        
        # Create alpha channel based on the mask
        b, g, r, a = cv2.split(foreground)
        alpha_channel = cv2.bitwise_and(a, a, mask=mask_inv)
        foreground_with_alpha = cv2.merge([b, g, r, alpha_channel])
        
        # Save the result
        cv2.imwrite(image_path, foreground_with_alpha)

        # Convert image dpi => 200
        with Image.open(image_path) as img:
            img.save(image_path, dpi=(200, 200))

        base64_string = image_to_base64(image_path)
        os.remove(image_path)
        
        url = processAndSaveImage(base64_string, img_id)
        return url
    except Exception as error:
        logger.error(f"Error in printful_utils : {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )


def processAndSaveImage(image_data: str, img_id: str):
    try:
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # if image.mode == 'RGBA':
        # image = image.convert('RGB')

        buffered = io.BytesIO()
        # image.save(buffered, format="JPEG", quality=85)
        image.save(buffered, format="PNG", quality=100)
        compressed_image_bytes = buffered.getvalue()
        s3_client = boto3.client(
            "s3", region_name="us-east-2", config=Config(signature_version="s3v4")
        )

        image_key = f"{img_id}.jpg"
        s3_bucket_name = "masked-images"

        s3_client.upload_fileobj(
            io.BytesIO(compressed_image_bytes),
            s3_bucket_name,
            image_key,
            # ExtraArgs={"ACL": "public-read", "ContentType": "image/jpeg", "ContentDisposition": "inline"},
            ExtraArgs={"ContentType": "image/png", "ContentDisposition": "inline"},
        )

        url = generate_presigned_url(img_id, "masked-images")
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


def printful_request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {PRIVATE_TOKEN}",
        "Content-Type": "application/json",
    }

    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError("Unsupported HTTP method")

    if response.status_code not in range(200, 299):
        raise Exception(
            f"Request failed with status code {response.status_code}: {response.text}"
        )

    return response.json()


def get_store_products():
    return printful_request("/store/products")["result"]


def get_product_variants(product_id):
    return printful_request(f"/store/products/{product_id}")["result"]["sync_variants"]


def products_and_variants_map():
    product_map = {}
    products = get_store_products()

    for product in products:
        product_id = product["id"]
        product_name = product["name"].lower().replace(" ", "_").replace("-", "")
        product_map[product_name] = {
            "size_map": {},
            "size": [],
            "color_map": {},
            "variants": {},
        }

        variants = get_product_variants(product_id)

        for variant in variants:
            size = variant["size"]
            color = variant["color"]
            variant_id = variant["variant_id"]

            if size not in product_map[product_name]["size"]:
                product_map[product_name]["size"].append(size)
            if size not in product_map[product_name]["variants"]:
                product_map[product_name]["variants"][size] = {}

            if color.lower() not in product_map[product_name]["color_map"]:
                product_map[product_name]["color_map"][color.lower()] = color

            product_map[product_name]["variants"][size][color] = variant_id

    if "cap" in product_map:
        product_map["cap"]["size_map"] = {
            "m": "One size",
            "M": "One size",
            "XS": "One size",
        }
        product_map["cap"]["color_map"] = {
            "black": "Black",
            "navy blue": "Pacific",
            "dark gray": "Charcoal",
            "beige": "Oyster",
        }

    if "mug" in product_map:
        product_map["mug"]["size_map"] = {"m": "11 oz", "M": "11 oz"}

    if "tshirt" in product_map:
        product_map["tshirt"]["color_map"] = {
            "black": "Black",
            "brick": "Brick Red",
            "carbon": "Carbon Grey",
            "white": "White",
        }

    return product_map
