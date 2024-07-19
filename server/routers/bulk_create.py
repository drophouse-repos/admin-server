from fastapi import APIRouter, HTTPException, Depends
from models.bulkordermodel import BulkOrderRequest
from models.OrderItemModel import OrderItem
from models.ShippingModel import ShippingModel
from models.ItemModel import ItemModel
from ai_models.utils import generate_prompts, generate_images
from routers.order_info import PlaceOrderDataRequest, place_order
from aws_utils import generate_presigned_url, processAndSaveImage
from inspect import currentframe, getframeinfo
from database.OrderOperations import OrderOperations
from database.PricesOperations import PricesOperations
from database.BASE import BaseDatabaseOperation
from db import get_db_ops
import traceback
from typing import List
import datetime
import random
import logging
import uuid

bulk_order_router = APIRouter()
HARD_CODED_PASSWORD = "Drophouse23#"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        user_data = request.file
        for idx in range(len(user_data)):
            imageresponse = response_data[idx]
            if isinstance(imageresponse, Exception) or imageresponse == None:
                logger.info(f"Image Generation failed : retrying ...")
                imageresponse = await generate_failed_image(request.prompts)
                
            order_id = str(uuid.uuid4())
            if 'order_id' in user_data[idx]:
                order_id = user_data[idx]['order_id']

            order_model = OrderItem(
                user_id = user_data[idx]['email'],
                user_type = user_data[idx]['user_type'],
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

async def generate_failed_image(prompts: List[str]):
    logger.info(f"Image Generation failed : retrying begin")
    generated_data = await generate_prompts([random.choice(prompts)], 1)
    response_data = await generate_images(generated_data)

    imageresponse = response_data[0]
    if isinstance(imageresponse, Exception) or imageresponse == None:
        logger.info(f"Image Generation failed : retrying failed")
        return await generate_failed_image(prompts)

    logger.info(f"Image Generation failed : retrying success")
    return imageresponse