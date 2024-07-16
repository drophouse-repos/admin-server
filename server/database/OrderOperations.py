from datetime import datetime, timedelta
import logging
from database.BASE import BaseDatabaseOperation
from models.OrderItemModel import OrderItem
from aws_utils import generate_presigned_url
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderOperations(BaseDatabaseOperation):
    async def create(self, user_id: str, order_info: OrderItem) -> bool:
        try:
            order_data = order_info.model_dump()
            user_update_result = await self.db.users.update_one(
                {"user_id": user_id}, {"$push": {"orders": order_data}}
            )

            orders_insert_result = await self.db.orders.insert_one(order_data)
            return (
                user_update_result.modified_count > 0
                and orders_insert_result.inserted_id is not None
            )
        except Exception as e:
            logger.critical(f"Error adding to order: {e}")
            return False

    async def remove(self, user_id: str, order_info: OrderItem) -> bool:
        try:
            order_id = order_info.order_id
            user_update_result = await self.db.users.update_one(
                {"user_id": user_id}, {"$pull": {"orders": {"_id": order_id}}}
            )
            orders_delete_result = await self.db.orders.delete_one(
                {"order_id": order_id}
            )
            return (
                user_update_result.modified_count > 0
                and orders_delete_result.deleted_count > 0
            )
        except Exception as e:
            logger.critical(f"Error in removing order: {e}")
            return False

    async def update(self, user_id: str, updated_order_info: OrderItem):
        try:
            updated_order_data = updated_order_info.model_dump()
            order_id = updated_order_info.order_id

            user_update_result = await self.db.users.update_one(
                {"user_id": user_id, "orders.order_id": order_id},
                {"$set": {"orders.$": updated_order_data}},
            )

            orders_update_result = await self.db.orders.update_one(
                {"order_id": order_id}, {"$set": updated_order_data}
            )
            return (
                user_update_result.modified_count > 0
                and orders_update_result.modified_count > 0
            )
        except Exception as e:
            logger.critical(f"Error in updating order: {e}")
            return False

    async def get(self, user_id: str) -> list:
        try:
            user = await self.db.users.find_one({"user_id": user_id}, {"orders": 1})
            if user and "orders" in user:
                for order in user["orders"]:
                    for item in order["item"]:
                        img_id = item["img_id"]
                        thumbnail_img_id = "t_" + img_id
                        item["thumbnail"] = generate_presigned_url(thumbnail_img_id, "thumbnails-cart")
                return user["orders"]
            else:
                return []
        except Exception as e:
            logger.error(f"Error retrieving orders: {e}")
            return []
        
    async def getByOrderID(self, order_id: str):
        try:
            raw_order = await self.db.orders.find_one({"order_id": order_id})
            order = OrderItem(**raw_order)
            return order
        except Exception as e:
            logger.error(f"Error retrieving orders: {e}")
            print("order not found")
            return
        
    async def update_order_status(self, user_id: str, order_id: str, new_status: str):
        try:
            user_update_result = await self.db.users.update_one(
                {"user_id": user_id, "orders.order_id": order_id},
                {"$set": {"orders.$.status": new_status}},
            )

            orders_update_result = await self.db.orders.update_one(
                {"order_id": order_id},
                {"$set": {"status": new_status}},
            )

            return (
                user_update_result.modified_count > 0
                and orders_update_result.modified_count > 0
            )
        except Exception as e:
            logger.critical(f"Error updating order status: {e}")
            return False
        
    async def remove_unpaid_order(self, user_id: str):
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            result = await self.db.orders.delete_many({
                "timestamp": {"$lt": one_hour_ago},
                "status": "unpaid"
            })
            user_update_result = await self.db.users.update_one(
                {"user_id": user_id}, {"$pull": {"orders":{
                "timestamp": {"$lt": one_hour_ago},
                "status": "unpaid"
                }}}
            ) 
            return result
        except Exception as e:
            logger.critical(f"Error updating order status: {e}")
            return False
        
    async def create_bulk(self, orders: List[OrderItem]) -> bool:
        try:
            order_data_list = [order.model_dump() for order in orders]
            orders_insert_result = await self.db.orders.insert_many(order_data_list)
            return orders_insert_result.inserted_ids is not None
        except Exception as e:
            logger.critical(f"Error adding bulk orders: {e}")
            return False
