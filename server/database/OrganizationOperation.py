import logging
from aws_utils import generate_presigned_url
from database.BASE import BaseDatabaseOperation
from models import OrganizationModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrganizationOperation(BaseDatabaseOperation):
    async def create(self, org_info: OrganizationModel) -> bool:
        try:
            org_data = org_info.model_dump()
            result = await self.db.organizations.insert_one(org_data)
            return result.inserted_id is not None
        except Exception as e:
            logger.critical(f"Error adding organizations data to db: {e}")
            return False

    async def remove(self) -> bool:
        pass

    async def update(self, org_info: OrganizationModel) -> bool:
        try:
            org_data = org_info.model_dump()
            org_id = org_info.org_id

            result = await self.db.organizations.update_one(
                {"org_id": org_id},
                {"$set": org_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.critical(f"Error in updating organization: {e}")
            return False

    async def get(self):
        try:
            s3_bucket = 'drophouse-skeleton'
            org_data = await self.db.organizations.find({}, {'_id': 0}).to_list(length=None)
            if org_data:
                org_dict = {}
                for org in org_data:
                    if 'mask' in org and org['mask'] != None and org['mask'] != 'null' and org['mask'] != '':
                        org['mask'] = generate_presigned_url(org['mask'], s3_bucket)
                    if 'logo' in org and org['logo'] != None and org['logo'] != 'null' and org['logo'] != '':
                        org['logo'] = generate_presigned_url(org['logo'], s3_bucket)
                    if 'greenmask' in org and org['greenmask'] != None and org['greenmask'] != 'null' and org['greenmask'] != '':
                        org['greenmask'] = generate_presigned_url(org['greenmask'], s3_bucket)
                    if 'favicon' in org and org['favicon'] != None and org['favicon'] != 'null' and org['favicon'] != '':
                        org['favicon'] = generate_presigned_url(org['favicon'], s3_bucket)

                    for products in org['landingpage']:
                        if 'asset' in products and products['asset'] != None and products['asset'] != 'null' and products['asset'] != '':
                            products['asset'] = generate_presigned_url(products['asset'], s3_bucket)
                        if 'asset_back' in products and products['asset_back'] != None and products['asset_back'] != 'null' and products['asset_back'] != '':
                            products['asset_back'] = generate_presigned_url(products['asset_back'], s3_bucket)

                    for product in org['products']:
                        if 'mask' in product and product['mask'] != None and product['mask'] != 'null' and product['mask'] != '':
                            product['mask'] = generate_presigned_url(product['mask'], s3_bucket)
                        if 'greenmask' in product and product['greenmask'] != None and product['greenmask'] != 'null' and product['greenmask'] != '':
                            product['greenmask'] = generate_presigned_url(product['greenmask'], s3_bucket)
                        if 'defaultProduct' in product and product['defaultProduct'] != None and product['defaultProduct'] != 'null' and product['defaultProduct'] != '':
                            product['defaultProduct'] = generate_presigned_url(product['defaultProduct'], s3_bucket)

                        for color in product['colors']:
                            if product['colors'][color]['asset']['front'] != None and product['colors'][color]['asset']['front'] != 'null' and product['colors'][color]['asset']['front'] != '':
                                product['colors'][color]['asset']['front'] = generate_presigned_url(product['colors'][color]['asset']['front'], s3_bucket)
                            if product['colors'][color]['asset']['back'] != None and product['colors'][color]['asset']['back'] != 'null' and product['colors'][color]['asset']['back'] != '':
                                product['colors'][color]['asset']['back'] = generate_presigned_url(product['colors'][color]['asset']['back'], s3_bucket)

                    org_dict[org['org_id']] = org
                return org_dict
            else:
                return {}
        except Exception as e:
            logger.error(f"Error retrieving organizations: {e}")
            return []

    async def get_by_id(self, org_id: int):
        try:
            org_data = await self.db.organizations.find_one({"org_id": org_id}, {'_id': 0})
            return org_data
        except Exception as e:
            logger.error(f"Error retrieving organization with ID {org_id}: {e}")
            return None
    
    async def get_organization_data(self,org_id: str):
        organization = await self.db.organizations.find_one({"org_id": org_id})  # Replace 'organizations' with your collection name
        if not organization:
            logger.error(f"Error retrieving organization with ID {org_id}")
        return organization
    
    async def delete_organization_data(self,org_id: str):
        result = await self.db.organizations.delete_one({"org_id": org_id})
        if result.deleted_count == 0:
            logger.error(f"Error removing organization data with ID {org_id}")
        else:
            logger.info(f"Organization with ID: {org_id}, Deleted Successfully!!!")
        return result
