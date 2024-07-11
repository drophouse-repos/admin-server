import logging
from database.BASE import BaseDatabaseOperation
from models import PricesModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PricesOperations(BaseDatabaseOperation):
	async def create(self, price_info: PricesModel) -> bool:
		try:
			price_data = price_info.model_dump()
			result = await self.db.Prices.insert_one(price_data)
			return result.modified_count > 0
		except Exception as e:
			logger.critical(f"Error adding price to prices: {e}")
			return False

	async def remove(self, apparel: str) -> bool:
		try:
			result = await self.db.Prices.delete_one(
				{"apparel":apparel}
			)
			return result.modified_count > 0
		except Exception as e:
			logger.critical(f"Error removing price in prices: {e}")
			return False

	async def update(self, apparel):
		# Implementation for updating if needed
		pass

	async def get(self):
		try:
			prices_data = await self.db.Prices.find({}, {'_id':0}).to_list(length=None)
			if prices_data:
				prices_dict = {price['apparel']: price['price'] for price in prices_data}
				return prices_dict
			else:
				return []
		except Exception as e:
			logger.error(f"Error retrieving prices: {e}")
			return []