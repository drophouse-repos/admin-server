import logging
import asyncio
import base64
import sys
import os
from PIL import Image
import io
import boto3

import traceback
from inspect import currentframe, getframeinfo
from fastapi import HTTPException
from botocore.exceptions import NoCredentialsError
from botocore.client import Config
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_ops, connect_to_mongo, close_mongo_connection, get_database
from models.OrganizationModel import OrganizationModel
from database.BASE import BaseDatabaseOperation
# from aws_utils import processAndSaveImage
# from utils.printful_util import processAndSaveImage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

s3_bucket_name = 'drophouse-skeleton'
class OrganizationMigration(BaseDatabaseOperation):
    def __init__(self, db):
        super().__init__(db)

    async def create(self):
        pass
    
    async def update(self):
        pass
    
    async def remove(self):
        pass
    
    async def get(self):
        pass
    
    async def start_migrate(self):
        start = datetime.now()
        # organizations = await self.db.organizations.find({"org_id": "bhzbJJK20zQqT2Xo"}, {'_id': 0}).to_list(length=None)
        organizations = await self.db.organizations.find({}, {'_id': 0}).to_list(length=None)
        duration = datetime.now() - start
        print(f'Duration : {duration}')
        print(len(organizations))

        updated_organizations = []  # To store updated organization objects
        for org in organizations:
            org_id = org['org_id']
            print('Processing org_id:', org_id)
            
            if 'products' not in org or 'landingpage' not in org:
                continue
                
            # Process mask
            if 'mask' in org:
                org_mask = org['mask']
                if isinstance(org_mask, bytes) and org_mask.startswith(b'data:image'):
                    org_mask = org_mask.decode('utf-8')
                if org_mask and org_mask.startswith("data:image"):
                    processAndSaveImage(org_mask, f"mask_{org_id}", s3_bucket_name)
                    org['mask'] = f"mask_{org_id}"

            # Process logo
            if 'logo' in org:
                org_logo = org['logo']
                if isinstance(org_logo, bytes) and org_logo.startswith(b'data:image'):
                    org_logo = org_logo.decode('utf-8')
                if org_logo and org_logo.startswith("data:image"):
                    processAndSaveImage(org_logo, f"logo_{org_id}", s3_bucket_name)
                    org['logo'] = f"logo_{org_id}"

            # Process greenmask
            if "greenmask" in org:
                org_gm = org["greenmask"]
                if isinstance(org_gm, bytes) and org_gm.startswith(b'data:image'):
                    org_gm = org_gm.decode('utf-8')
                if org_gm and org_gm.startswith("data:image"):
                    processAndSaveImage(org_gm, f"gm_{org_id}", s3_bucket_name)
                    org["greenmask"] = f"gm_{org_id}"
            
            # Process favicon
            if 'favicon' in org:
                org_favicon = org["favicon"]
                if isinstance(org_favicon, bytes) and org_favicon.startswith(b'data:image'):
                    org_favicon = org_favicon.decode('utf-8')
                if org_favicon and org_favicon.startswith("data:image"):
                    processAndSaveImage(org_favicon, f"favicon_{org_id}", s3_bucket_name)
                    org["favicon"] = f"favicon_{org_id}"

            # Process landing page assets
            if 'landingpage' in org:
                for product in org["landingpage"]:
                    if 'asset' in product and isinstance(product['asset'], bytes) and product['asset'].startswith(b'data:image'):
                        product['asset'] = product['asset'].decode('utf-8')
                    if product['asset'] and product['asset'].startswith("data:image"):
                        processAndSaveImage(product['asset'], f"lp_{product['name']}_{org_id}", s3_bucket_name)
                        product['asset'] = f"lp_{product['name']}_{org_id}"

                    if 'asset_back' not in product:
                        print('Missing asset_back org_id:', org_id)
                    if 'asset_back' in product and isinstance(product['asset_back'], bytes) and product['asset_back'].startswith(b'data:image'):
                        product['asset_back'] = product['asset_back'].decode('utf-8')
                    if 'asset_back' in product and product['asset_back'] and product['asset_back'].startswith("data:image"):
                        processAndSaveImage(product['asset_back'], f"lp_{product['name']}_{org_id}", s3_bucket_name)
                        product['asset_back'] = f"lp_{product['name']}_{org_id}"

            # Process product details
            if 'products' in org:
                for product in org["products"]:
                    # Mask
                    if 'mask' in product and isinstance(product['mask'], bytes) and product['mask'].startswith(b'data:image'):
                        product['mask'] = product['mask'].decode('utf-8')
                    if product['mask'] and product['mask'].startswith("data:image"):
                        processAndSaveImage(product['mask'], f"p_{product['name']}_mask_{org_id}", s3_bucket_name)
                        product['mask'] = f"p_{product['name']}_mask_{org_id}"
                    
                    # Default Product Image
                    if 'defaultProduct' in product and isinstance(product['defaultProduct'], bytes) and product['defaultProduct'].startswith(b'data:image'):
                        product['defaultProduct'] = product['defaultProduct'].decode('utf-8')
                    if product['defaultProduct'] and product['defaultProduct'].startswith("data:image"):
                        processAndSaveImage(product['defaultProduct'], f"p_{product['name']}_dp_{org_id}", s3_bucket_name)
                        product['defaultProduct'] = f"p_{product['name']}_dp_{org_id}"

                    # Colors
                    for color, color_data in product['colors'].items():
                        if 'asset' in color_data:
                            # Front
                            if isinstance(color_data['asset'].get('front'), bytes) and color_data['asset']['front'].startswith(b'data:image'):
                                color_data['asset']['front'] = color_data['asset']['front'].decode('utf-8')
                            if color_data['asset'].get('front', '').startswith("data:image"):
                                processAndSaveImage(color_data['asset']['front'], f"pf_{product['name']}_{color}_{org_id}", s3_bucket_name)
                                color_data['asset']['front'] = f"pf_{product['name']}_{color}_{org_id}"

                            # Back
                            if isinstance(color_data['asset'].get('back'), bytes) and color_data['asset']['back'].startswith(b'data:image'):
                                color_data['asset']['back'] = color_data['asset']['back'].decode('utf-8')
                            if color_data['asset'].get('back', '').startswith("data:image"):
                                processAndSaveImage(color_data['asset']['back'], f"pb_{product['name']}_{color}_{org_id}", s3_bucket_name)
                                color_data['asset']['back'] = f"pb_{product['name']}_{color}_{org_id}"

            # Convert to Pydantic model
            org_model = OrganizationModel(**org)
            org_data = org_model.model_dump()

            # Update the organization in the database
            result = await self.db.organizations.update_one(
                {"org_id": org_id},
                {"$set": org_data}
            )
            
            if result.modified_count > 0:
                updated_organizations.append(org_data)
            else:
                logger.info(f"No changes made for org_id: {org_id}")

        print('Organizations processed:', len(updated_organizations))
        return updated_organizations

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

async def migrate_base64image_to_s3bucket(db_ops: OrganizationMigration):
    try:
        result = await db_ops.start_migrate()
        return result
    except Exception as e:
        logger.error(f"Error in getting Organization: {str(e)}", exc_info=True)
        raise Exception("Internal Server Error")

if __name__ == "__main__":
    asyncio.run(connect_to_mongo())
    db_instance = get_database()
    organization_migration = OrganizationMigration(db_instance)
    asyncio.run(migrate_base64image_to_s3bucket(organization_migration))
    asyncio.run(close_mongo_connection())
