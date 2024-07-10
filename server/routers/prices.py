import logging
import traceback
# from verification import verify_id_token
from inspect import currentframe, getframeinfo

from db import get_db_ops
from database.BASE import BaseDatabaseOperation
from models.PricesModel import PricesModel
from database.PricesOperations import PricesOperations
from fastapi import APIRouter, HTTPException, Depends

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

prices_router = APIRouter()

@prices_router.post("/get_prices")
async def get_prices(
    # user_id: str = Depends(verify_id_token),
	db_ops: BaseDatabaseOperation = Depends(get_db_ops(PricesOperations)),
):
    try:
        # if not user_id:
            # raise HTTPException(status_code=401, detail={'message':"User ID is required.", 'currentFrame': getframeinfo(currentframe())})
        result = await db_ops.get()
        return result;
    except Exception as e:
        logger.error(f"Error in get prices: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message':"Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})
