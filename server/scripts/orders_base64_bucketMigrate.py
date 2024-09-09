import logging
import asyncio
import base64
import sys
import os

from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_ops, connect_to_mongo, close_mongo_connection, get_database
from database.BASE import BaseDatabaseOperation
from models.OrderItemModel import OrderItem
from aws_utils import processAndSaveImage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

s3_bucket_name = 'browse-image-v2'
s3_thumbnail_bucket = "thumbnails-cart"
class OrderMigration(BaseDatabaseOperation):
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
        # orders = await self.db.orders.find({"order_id": "6d82786d-f3c7-477b-8a4a-a53a8469550d"}, {'_id': 0}).to_list(length=None)
        orders = await self.db.orders.find({}, {'_id': 0}).to_list(length=None)
        duration = datetime.now() - start
        print(f'Duration : {duration}')
        print(len(orders))

        updated_orders = []  # To store updated order objects
        for order in orders:
            order_id = order['order_id']
            print('Processing order_id:', order_id)
            
            # Process landing page assets
            if 'item' in order:
                for item in order["item"]:
                    img_id = item['img_id']
                    if 'thumbnail' in item and isinstance(item['thumbnail'], bytes) and item['thumbnail'].startswith(b'data:image'):
                        item['thumbnail'] = item['thumbnail'].decode('utf-8')
                    if item['thumbnail'] and item['thumbnail'].startswith("data:image"):
                        thumbnail_img_id = "t_" + img_id
                        processAndSaveImage(item['thumbnail'], thumbnail_img_id, s3_thumbnail_bucket)
                        item['thumbnail'] = thumbnail_img_id

                    if 'toggled' in item and isinstance(item['toggled'], bytes) and item.toggled.startswith(b'data:image'):
                        item['toggled'] = item['toggled'].decode('utf-8')
                    if item['toggled'] and type(item['toggled']) == str and item['toggled'].startswith("data:image"):
                        toggled_img_id = "e_" + img_id
                        processAndSaveImage(item['toggled'], toggled_img_id, s3_bucket_name)
                        item['toggled'] = toggled_img_id

            # Convert to Pydantic model
            order_model = OrderItem(**order)
            order_data = order_model.model_dump()

            # print(order_data)
            # Update the order to the database
            result = await self.db.orders.update_one(
                {"order_id": order_id},
                {"$set": order_data}
            )
            
            if result.modified_count > 0:
                updated_orders.append(order_data)
            else:
                logger.info(f"No changes made for order_id: {order_id}")

        print('Order processed:', len(updated_orders))
        return updated_orders

async def migrate_base64image_to_s3bucket(db_ops: OrderMigration):
    try:
        result = await db_ops.start_migrate()
        return result
    except Exception as e:
        logger.error(f"Error in getting Orders: {str(e)}", exc_info=True)
        raise Exception("Internal Server Error")

if __name__ == "__main__":
    asyncio.run(connect_to_mongo())
    db_instance = get_database()
    order_migration = OrderMigration(db_instance)
    asyncio.run(migrate_base64image_to_s3bucket(order_migration))
    asyncio.run(close_mongo_connection())
