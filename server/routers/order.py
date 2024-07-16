import datetime
import uuid
import logging
import traceback
from typing import List
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from models.OrderItemModel import OrderItem
from models.ItemModel import ItemModel
from models.ShippingModel import ShippingModel
from database.OrderOperations import OrderOperations
from verification import verify_id_token
from database.BASE import BaseDatabaseOperation
from db import get_db_ops

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
order_info_router = APIRouter()

@order_info_router.post("/upload_excel")
async def upload_excel(
    user_type: str,
    org_id: str,
    org_name: str,
    user_id: str,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
    file: UploadFile = File(...),
):
    try:
        df = pd.read_excel(file.file)
        orders = []

        for index, row in df.iterrows():
            item = [ItemModel(
                apparel=row['item_apparel'],
                size=row['item_size'],
                color=row['item_color'],
                img_id=row['item_img_id'],
                prompt=row['item_prompt'],
                timestamp=row['item_timestamp'],
                thumbnail=row['item_thumbnail'],
                toggled=row['item_toggled'],
                price=row['item_price'],
            )]
            shipping_info = ShippingModel(
                firstName=row['shipping_info_firstName'],
                lastName=row['shipping_info_lastName'],
                email=row['shipping_info_email'],
                phone=row['shipping_info_phone'],
                streetAddress=row['shipping_info_streetAddress'],
                streetAddress2=row['shipping_info_streetAddress2'],
                city=row['shipping_info_city'],
                stateProvince=row['shipping_info_stateProvince'],
                postalZipcode=row['shipping_info_postalZipcode'],
                addressType=row['shipping_info_addressType'],
            )
            order_id = str(uuid.uuid4())
            timestamp = datetime.datetime.utcnow()

            order_info = OrderItem(
                user_id=user_id,
                user_type=user_type,
                org_id=org_id,
                org_name=org_name,
                order_id=order_id,
                item=item,
                shipping_info=shipping_info,
                status="pending",
                timestamp=timestamp,
            )
            orders.append(order_info)

        result = await db_ops.create_bulk(orders)
        if not result:
            raise HTTPException(status_code=404, detail=f"Bulk order creation failed for user {user_id}.")

        return {"message": "Orders uploaded successfully", "order_ids": [order.order_id for order in orders]}
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in upload_excel: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(traceback.format_exc()))
