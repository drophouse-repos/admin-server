import logging
import traceback
from inspect import currentframe, getframeinfo

from db import get_db_ops
from database.BASE import BaseDatabaseOperation
from models.OrganizationModel import OrganizationModel
from database.OrganizationOperation import OrganizationOperation
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from bson import ObjectId
from pydantic import BaseModel
import aiohttp
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

org_router = APIRouter()

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

async def fetch_image_as_base64(image_url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch image")
            image_data = await response.read()
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
            return {"color_asset": color_asset,"Dim_Left": Dim_Left,"Dim_Top": Dim_Top,"Dim_height": Dim_height,"Dim_width": Dim_width,"mock_img": mock_img}

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
		result = await db_ops.create(request)
		return result;
	except Exception as e:
		logger.error(f"Error in creating Organization: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

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

