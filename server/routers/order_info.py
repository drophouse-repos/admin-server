import datetime
import json
from typing import List
import uuid
import logging
import traceback
from inspect import currentframe, getframeinfo
from fastapi import APIRouter, Body, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr
from dotenv import load_dotenv
from database.BASE import BaseDatabaseOperation
from db import get_db_ops
from fastapi import Depends
from models.OrderItemModel import OrderItem
from database.OrderOperations import OrderOperations
from models.ItemModel import ItemModel
from models.ShippingModel import ShippingModel
from database.UserOperations import UserOperations
from verification import verify_id_token
from bson import json_util

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
order_info_router = APIRouter()

class PlaceOrderDataRequest(BaseModel):
    shipping_info: ShippingModel
    item: List[ItemModel]


async def place_order(
    request: PlaceOrderDataRequest, user_id: str, usertype:str, 
    org_id:str,
    org_name:str,
    db_ops: BaseDatabaseOperation = OrderOperations,
):
    try:
        item = request.item
        shipping_info = request.shipping_info
        order_id = str(uuid.uuid4())
        timestamp = datetime.datetime.utcnow()
        order_info = OrderItem(
            user_id=user_id,
            user_type=usertype,
            org_id = org_id,
            org_name = org_name,
            order_id=order_id,
            item=item,
            shipping_info=shipping_info,
            status="unpaid",
            timestamp=timestamp,
        )
        result = await db_ops.create(user_id, order_info)

        if result:
            return order_id
        else:
            raise HTTPException(status_code=404, detail={'message': "User not found or no order placed", 'currentFrame': getframeinfo(currentframe())})
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in place_order: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})


@order_info_router.post("/update_order")
async def update_order(
    order_info: OrderItem,
    user_id: str = Depends(verify_id_token),
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
):
    try:
        result = await db_ops.update(user_id, order_info)

        if result:
            return {"message": "Order Updated!"}
        else:
            raise HTTPException(status_code=404, detail={'message': "User not found or no order updated", 'currentFrame': getframeinfo(currentframe())})
    except HTTPException as http_ex:
        # HTTP exceptions should be raised directly
        raise http_ex
    except Exception as e:
        logger.error(f"Error in update_order: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})


@order_info_router.get("/get_order_history")
async def get_order_history(
    user_id: str = Depends(verify_id_token),
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
):
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail={'message': "User ID is required.", 'currentFrame': getframeinfo(currentframe())})
        await db_ops.remove_unpaid_order(user_id)
        order_history = await db_ops.get(user_id)
        return {"order_history": order_history}
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in get_order_history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})