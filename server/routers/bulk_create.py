from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from models.bulkordermodel import BulkOrderRequest
from models.OrderItemModel import OrderItem
from models.ShippingModel import ShippingModel
from models.ItemModel import ItemModel
from ai_models.utils import generate_prompts, generate_images
from routers.order_info import PlaceOrderDataRequest, place_order
from fastapi.responses import JSONResponse, FileResponse
from aws_utils import generate_presigned_url, processAndSaveImage
from inspect import currentframe, getframeinfo
from database.OrderOperations import OrderOperations
from database.UserOperations import UserOperations
from database.PricesOperations import PricesOperations
from database.BASE import BaseDatabaseOperation
from db import get_db_ops
import traceback
from typing import List
import datetime
import random
from bson import json_util
import logging
import uuid
import os
from utils.printful_util import (
    applyMask_and_removeBackground_file
)
from utils.generate_vector_ai import (
    generate_zip_pre,
    generate_pdf_pre,
    clean_old_data_prepared
)

bulk_order_router = APIRouter()
HARD_CODED_PASSWORD = "Drophouse23#"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

min_retry = 10

@bulk_order_router.post("/bulk-download-prepared_orders")
async def bulk_prepare(
    background_tasks: BackgroundTasks,
    order_ids: List[str],
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
    order_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
):
    try:
        clear_old = await clean_old_data_prepared()
        mask_image_path = "./images/masks/elephant_mask.png"
        result = await db_ops.get_student_order(order_ids)
        if result:
            for order in result:
                if "images" in order:
                    for image in order["images"]:
                        size = image.split("_", 1)[0]
                        zip_folder1 = f"../student_module_zip_download1/temp_student_products/{size}"
                        if not os.path.exists(zip_folder1):
                            os.makedirs(zip_folder1)
                        image_path = f"{zip_folder1}/{image}.png"
                        image_data = applyMask_and_removeBackground_file(
                            order["images"][image]["img_path"],
                            mask_image_path,
                            order["images"][image]["img_id"],
                            image_path
                        )
                        
                        is_updated = await db_ops.update(order["user_id"], order["order_id"], "shipped")
                        if is_updated:
                            logger.info(f"Status updated : {image}")
                        else:
                            logger.error(f"Not able to update status, Error: {image}")
        zip_path = await generate_pdf_pre(background_tasks)
        if not os.path.exists(zip_path):
            return JSONResponse(
                content=json_util.dumps({"error": f"File not found: {zip_path}"})
            )

        return FileResponse(zip_path, filename=f"prepared_orders.zip")

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

@bulk_order_router.post("/bulk-order")
async def make_bulk_order(
    request: BulkOrderRequest,
    order_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
    price_db_ops: BaseDatabaseOperation = Depends(get_db_ops(PricesOperations)),
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        generated_data = await generate_prompts(request.prompts, request.numImages)
        response_data = await generate_images(generated_data)

        retry = 0
        user_data = request.file
        retry_limit = int(len(user_data)/2) if int(len(user_data)/2) > min_retry else min_retry
        for idx in range(len(user_data)):
            imageresponse = response_data[idx]
            if isinstance(imageresponse, Exception) or imageresponse == None:
                if retry > retry_limit:
                    raise HTTPException(status_code=400, detail={'message': "Image regeneration thershold reached", 'currentFrame': getframeinfo(currentframe())})
                logger.info(f"Image Generation failed : retrying [{retry}/{retry_limit}]")
                imageresponse, retry = await generate_failed_image(request.prompts, retry, retry_limit)
                
            order_id = str(uuid.uuid4())
            if 'order_id' in user_data[idx]:
                order_id = user_data[idx]['order_id']

            order_model = OrderItem(
                user_id = user_data[idx]['email'],
                user_type = user_data[idx]['user_type'],
                org_id = user_data[idx]['org_id'],
                org_name = user_data[idx]['org_name'],
                autogenerated = True,
                order_id = order_id,
                status = 'pending',
                timestamp = datetime.datetime.utcnow(),
                shipping_info = ShippingModel(
                    firstName = user_data[idx]['first_name'],
                    lastName = user_data[idx]['last_name'],
                    email = user_data[idx]['email'],
                    phone = user_data[idx]['phone'],
                    streetAddress = user_data[idx]['streetAddress'],
                    streetAddress2 = user_data[idx]['streetAddress2'],
                    city = user_data[idx]['city'],
                    stateProvince = user_data[idx]['state'],
                    postalZipcode = user_data[idx]['postalZipcode'],
                    addressType = 'primary'
                ),
                item = [ItemModel(
                    apparel = user_data[idx]['apparel'],
                    size = user_data[idx]['shirt-size'],
                    color = user_data[idx]['color'],
                    img_id = imageresponse[1],
                    prompt = imageresponse[2],
                    timestamp = datetime.datetime.utcnow(),
                    thumbnail = 'false',
                    toggled = False,
                    price = user_data[idx]['price']
                )]
            )
            user_data[idx]['img_id'] = imageresponse[1]
            user_data[idx]['prompt'] = imageresponse[2]

            if 'order_id' in user_data[idx]:
                result = await order_db_ops.update_order(order_model)
                if not result:
                    raise HTTPException(status_code=404, detail={'message': "Can't able to update an order", 'currentFrame': getframeinfo(currentframe())})
            else:
                result = await order_db_ops.create_order(order_model)
                if result:
                    user_data[idx]['order_id'] = order_id
                else:
                    raise HTTPException(status_code=404, detail={'message': "Can't able to create an order", 'currentFrame': getframeinfo(currentframe())})
        return user_data
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

async def generate_failed_image(prompts: List[str], retry: int, retry_limit: int):
    try:
        retry = retry + 1
        logger.info(f"Image Generation failed : retrying begin [{retry-1}/{retry_limit}]")
        generated_data = await generate_prompts([random.choice(prompts)], 1)
        response_data = await generate_images(generated_data)

        imageresponse = response_data[0]
        if isinstance(imageresponse, Exception) or imageresponse == None:
            logger.info(f"Image Generation failed : retrying failed [{retry-1}/{retry_limit}]")
            if retry > retry_limit:
                raise HTTPException(status_code=400, detail={'message': "Image regeneration thershold reached", 'currentFrame': getframeinfo(currentframe())})
            return await generate_failed_image(prompts, retry, retry_limit)

        logger.info(f"Image Generation failed : retrying success")
        return imageresponse, retry
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})