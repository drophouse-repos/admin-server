import logging
import traceback
from inspect import currentframe, getframeinfo

from db import get_db_ops
from database.BASE import BaseDatabaseOperation
from models.OrganizationModel import OrganizationModel
from aws_utils import generate_presigned_url #, processAndSaveImage
from database.OrganizationOperation import OrganizationOperation
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from bson import ObjectId
from pydantic import BaseModel
import httpx
import base64
import boto3
import io
from PIL import Image
from botocore.exceptions import NoCredentialsError
from botocore.client import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

org_router = APIRouter()
HARD_CODED_PASSWORD = "Drophouse23#"


def processAndSaveImage(image_data: str, img_id: str, s3_bucket_name_: str):
    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        else:
            raise ValueError("Invalid image data")

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
        s3_client.upload_fileobj(
            io.BytesIO(compressed_image_bytes),
            s3_bucket_name_,
            image_key,
            # ExtraArgs={"ACL": "public-read", "ContentType": "image/jpeg", "ContentDisposition": "inline"},
            ExtraArgs={"ContentType": "image/png", "ContentDisposition": "inline"},
        )

        return True
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

@org_router.post("/organisation_list")
async def organisation_list(
	db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation)),
):
	try:
		result = await db_ops.get()
		return result;
	except Exception as e:
		logger.error(f"Error in getting Organization: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

class OrgIdRequest(BaseModel):
    org_id: str
    apparel: str
    color: str
    img_url: str

async def fetch_image_as_base64(image_url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch image")
        image_data = response.content
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_data}"

@org_router.post("/get_org_data")
async def get_org_data(
	request_body: OrgIdRequest,
	org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation))
):
    try:
        org_id = request_body.org_id
        apparel = request_body.apparel
        color_name = request_body.color
        image_url = request_body.img_url
        organization_data = await org_db_ops.get_organization_data(org_id)
        if not organization_data:
              logger.error("No organisation is available with id : {org_id}")
              raise HTTPException(status_code=404, detail={'message':"No Organisation found"})
        else:
            default_product = next(
                (
                    product for product in organization_data['products']
                    if product['name'] == apparel and
                    isinstance(product['colors'], dict) and
                    any(color['name'] == color_name for color in product['colors'].values())
                ),
                None
            )
            color_asset = next(
                    (
                        color['asset']['front'] for color in default_product['colors'].values()
                        if color['name'] == color_name
                    ),
                    None
                )
            Dim_Left = default_product['dimensions']['left']
            Dim_Top = default_product['dimensions']['top']
            Dim_height = default_product['dimensions']['height']
            Dim_width = default_product['dimensions']['width']
            mock_img = default_product['mask']
            base64_image = await fetch_image_as_base64(image_url)
            return {"color_asset": color_asset,"Dim_Left": Dim_Left,"Dim_Top": Dim_Top,"Dim_height": Dim_height,"Dim_width": Dim_width,"mock_img": mock_img,"base64_img":base64_image}

    except Exception as e:
        logger.error(f"Error in getting Organization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                'message': "Internal Server Error",
                'currentFrame': getframeinfo(currentframe()),
                'detail': str(traceback.format_exc())
            }
        )		

@org_router.post("/create_organisation")
async def create_organisation(
	request : OrganizationModel,
	db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation)),
):
    try:
        org_bucket_name = 'drophouse-skeleton'
        org_id = request.org_id
        org_mask = request.mask
        if org_mask and org_mask.startswith("data:image"):
            processAndSaveImage(org_mask, f"mask_{org_id}", org_bucket_name)
            request.mask = f"mask_{org_id}"

        org_logo = request.logo
        if org_logo and org_logo.startswith("data:image"):
            processAndSaveImage(org_logo, f"logo_{org_id}", org_bucket_name)
            request.logo = f"logo_{org_id}"

        org_gm = request.greenmask
        if org_gm and org_gm.startswith("data:image"):
            processAndSaveImage(org_gm, f"gm_{org_id}", org_bucket_name)
            request.greenmask = f"gm_{org_id}"
        
        org_favicon = request.favicon
        if org_favicon and org_favicon.startswith("data:image"):
            processAndSaveImage(org_favicon, f"favicon_{org_id}", org_bucket_name)
            request.favicon = f"favicon_{org_id}"

        counter = 0
        for products in request.landingpage:
            counter += 1
            if products.asset and products.asset.startswith("data:image"):
                processAndSaveImage(products.asset, f"lp_{counter}_{products.name}_{org_id}", org_bucket_name)
                products.asset = f"lp_{counter}_{products.name}_{org_id}"
            if products.asset_back and products.asset_back.startswith("data:image"):
                processAndSaveImage(products.asset_back, f"lp_ab_{counter}_{products.name}_{org_id}", org_bucket_name)
                products.asset_back = f"lp_ab_{counter}_{products.name}_{org_id}"

        counter = 0
        for product in request.products:
            counter += 1
            if product.mask and product.mask.startswith("data:image"):
                processAndSaveImage(product.mask, f"p_{counter}_{product.name}_mask_{org_id}", org_bucket_name)
                product.mask = f"p_{counter}_{product.name}_mask_{org_id}"
            if product.defaultProduct and product.defaultProduct.startswith("data:image"):
                processAndSaveImage(product.defaultProduct, f"p_{counter}_{product.name}_dp_{org_id}", org_bucket_name)
                product.defaultProduct = f"p_{counter}_{product.name}_dp_{org_id}"

            for color in product.colors:
                if product.colors[color].asset.front and product.colors[color].asset.front.startswith("data:image"):
                    processAndSaveImage(product.colors[color].asset.front, f"pf_{counter}_{product.name}_{color}_{org_id}", org_bucket_name)
                    product.colors[color].asset.front = f"pf_{counter}_{product.name}_{color}_{org_id}"
                if product.colors[color].asset.back and product.colors[color].asset.back.startswith("data:image"):
                    processAndSaveImage(product.colors[color].asset.back, f"pb_{counter}_{product.name}_{color}_{org_id}", org_bucket_name)
                    product.colors[color].asset.back = f"pb_{counter}_{product.name}_{color}_{org_id}"

        result = await db_ops.create(request)
        return result;
    except Exception as e:
        logger.error(f"Error in creating Organization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

class OrgData(BaseModel):
    org_id: str
    password: str

@org_router.post("/delete_organisation")
async def delete_organisation(
     request: OrgData,
     db_ops: OrganizationOperation = Depends(get_db_ops(OrganizationOperation))
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        org_id = request.org_id
        result = await db_ops.delete_organization_data(org_id)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Organization not found")
        return {"success": True}
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@org_router.post("/update_organisation")
async def update_organisation(
    # org_id: str,
    request: OrganizationModel,
    db_ops: OrganizationOperation = Depends(get_db_ops(OrganizationOperation)),
):
    try:
        # Check if the organization with org_id exists before updating
        # existing_org = await db_ops.get_by_id(request)
        # if not existing_org:
        #     raise HTTPException(status_code=404, detail=f"Organization with ID not found")

        org_bucket_name = 'drophouse-skeleton'
        # uploading base64 img to bucket and change it to img_id
        org_id = request.org_id
        org_mask = request.mask
        if org_mask and org_mask.startswith("data:image"):
            processAndSaveImage(org_mask, f"mask_{org_id}", org_bucket_name)
            request.mask = f"mask_{org_id}"
        org_logo = request.logo
        if org_logo and org_logo.startswith("data:image"):
            processAndSaveImage(org_logo, f"logo_{org_id}", org_bucket_name)
            request.logo = f"logo_{org_id}"
        
        org_gm = request.greenmask
        if org_gm and org_gm.startswith("data:image"):
            processAndSaveImage(org_gm, f"gm_{org_id}", org_bucket_name)
            request.greenmask = f"gm_{org_id}"

        org_favicon = request.favicon
        if org_favicon and org_favicon.startswith("data:image"):
            processAndSaveImage(org_favicon, f"favicon_{org_id}", org_bucket_name)
            request.favicon = f"favicon_{org_id}"

        counter = 0
        for products in request.landingpage:
            counter += 1
            if products.asset and products.asset.startswith("data:image"):
                processAndSaveImage(products.asset, f"lp_{counter}_{products.name}_{org_id}", org_bucket_name)
                products.asset = f"lp_{counter}_{products.name}_{org_id}"
            if products.asset_back and products.asset_back.startswith("data:image"):
                processAndSaveImage(products.asset_back, f"lp_ab_{counter}_{products.name}_{org_id}", org_bucket_name)
                products.asset_back = f"lp_ab_{counter}_{products.name}_{org_id}"

        counter = 0
        for product in request.products:
            counter += 1
            if product.mask and product.mask.startswith("data:image"):
                processAndSaveImage(product.mask, f"p_{counter}_{product.name}_mask_{org_id}", org_bucket_name)
                product.mask = f"p_{counter}_{product.name}_mask_{org_id}"
            if product.defaultProduct and product.defaultProduct.startswith("data:image"):
                processAndSaveImage(product.defaultProduct, f"p_{counter}_{product.name}_dp_{org_id}", org_bucket_name)
                product.defaultProduct = f"p_{counter}_{product.name}_dp_{org_id}"

            for color in product.colors:
                if product.colors[color].asset.front and product.colors[color].asset.front.startswith("data:image"):
                    processAndSaveImage(product.colors[color].asset.front, f"pf_{counter}_{product.name}_{color}_{org_id}", org_bucket_name)
                    product.colors[color].asset.front = f"pf_{counter}_{product.name}_{color}_{org_id}"
                if product.colors[color].asset.back and product.colors[color].asset.back.startswith("data:image"):
                    processAndSaveImage(product.colors[color].asset.back, f"pb_{counter}_{product.name}_{color}_{org_id}", org_bucket_name)
                    product.colors[color].asset.back = f"pb_{counter}_{product.name}_{color}_{org_id}"

        # Update the organization
        updated_org = await db_ops.update(request)
        if not updated_org:
            raise HTTPException(status_code=400, detail="Failed to update organization")

        return {"success": True, "updated_organization": updated_org}

    except HTTPException as http_exception:
        raise http_exception

    except Exception as e:
        logger.error(f"Error in updating Organization with ID : {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'detail': str(traceback.format_exc())})

