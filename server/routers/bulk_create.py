from fastapi import APIRouter, HTTPException, Depends
from models.bulkordermodel import BulkOrderRequest
from models.OrderItemModel import OrderItem
from models.ShippingModel import ShippingModel
from models.ItemModel import ItemModel
from ai_models.utils import generate_prompts
from ai_models.utils import generate_images
from routers.order_info import PlaceOrderDataRequest, place_order
from aws_utils import generate_presigned_url, processAndSaveImage
from inspect import currentframe, getframeinfo
from database.OrderOperations import OrderOperations
from database.PricesOperations import PricesOperations
from database.BASE import BaseDatabaseOperation
from verification import verify_id_token
from db import get_db_ops
import traceback
import datetime
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
                img_id = 'blank'

            order_id = str(uuid.uuid4())
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
            result = await order_db_ops.create(user_data[idx]['email'], order_model)
            if result:
                user_data[idx]['order_id'] = order_id
            else:
                raise HTTPException(status_code=404, detail={'message': "User not found or no order placed", 'currentFrame': getframeinfo(currentframe())})
        return user_data
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})









# from fastapi import APIRouter, HTTPException, Depends
# from models.bulkordermodel import BulkOrderRequest
# from ai_models.utils import generate_prompts
# from ai_models.utils import generate_images
# from routers.order_info import PlaceOrderDataRequest, place_order
# from aws_utils import generate_presigned_url, processAndSaveImage
# from database.OrderOperations import OrderOperations
# from database.PricesOperations import PricesOperations
# from database.BASE import BaseDatabaseOperation
# from verification import verify_id_token
# from db import get_db_ops


# bulk_order_router = APIRouter()

# HARD_CODED_PASSWORD = "Drophouse23#"


# @bulk_order_router.post("/bulk-order")
# async def make_bulk_order(
#     request: BulkOrderRequest,
#     order_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
#     price_db_ops: BaseDatabaseOperation = Depends(get_db_ops(PricesOperations)),
#     user_id: str = Depends(verify_id_token),
# ):
#     if request.password != HARD_CODED_PASSWORD:
#         raise HTTPException(status_code=403, detail="Invalid password")
    
#     try:
#         generated_data = await generate_prompts(request.prompts, request.numImages)
#         image_id = await generate_images(generated_data)

#         shipping_info_meta = request.shipping_info
#         org_id = request.org_id
#         org_name = request.org_name

#         for item in image_id:
#             img_id = item[1]
#             thumbnail = False
#             thumbnail_img_id = "t_" + img_id
#             if thumbnail and thumbnail.startswith("data:image"):
#                 processAndSaveImage(thumbnail, thumbnail_img_id, "thumbnails-cart")

#         items = request.products
#         order_data_request = PlaceOrderDataRequest(shipping_info=shipping_info_meta, item=items)
#         order_id = await place_order(order_data_request, user_id, 'student', org_id, org_name, order_db_ops)
        
#         order_model = await order_db_ops.getByOrderID(order_id)
#         priceMap = await price_db_ops.get()
        
#         message_body = f'<div>\
#             <span><strong>User Name:</strong> {order_model.shipping_info.firstName} {order_model.shipping_info.lastName}</span><br>\
#             <span><strong>User Id:</strong> {order_model.user_id}</span><br><br>\
#             <span><strong>Order Id:</strong> {order_model.order_id}</span><br>\
#             <span><strong>Date & Time:</strong> {order_model.timestamp.strftime("%d/%m/%Y, %H:%M:%S")}</span<br><br>\
#             <span><strong>Address:</strong> {order_model.shipping_info.streetAddress} {order_model.shipping_info.streetAddress2}, {order_model.shipping_info.city}, \
#             {order_model.shipping_info.stateProvince} - {order_model.shipping_info.postalZipcode}</span><br>\
#             <span><strong>Email:</strong> {order_model.shipping_info.email}</span><br>\
#             <span><strong>Phone Number:</strong> {order_model.shipping_info.phone}</span><br>\
#             <br><hr><br>'

#         amount_total = 0
#         items = order_model.item
#         for item in items:
#             thumbnail_img_id = "t_" + item.img_id
#             thumbnail = generate_presigned_url(thumbnail_img_id, "thumbnails-cart")

#             message_body += f'<div style="display:flex">\
#                 <div style="order:1"><img src="{thumbnail}" style="width:150px; height:150px;"></div>\
#                 <div style="order:2; margin-left:15px;">\
#                     <span><strong>Item Type:</strong> {item.apparel}</span><br>'
#             if(item.apparel != "Mug" or item.apparel != "cap"):
#                 message_body += f'<span><strong>Item Size:</strong> {item.size}</span><br>'

#             message_body += f'<span><strong>Item Color:</strong> {item.color}</span><br><br>\
#                 <span><strong>Item img_id:</strong> {item.img_id}</span><br>\
#                 <span><strong>Item Prompt:</strong> {item.prompt}</span><br><br>\
#                 <span><strong>Item Price:</strong>$ {priceMap[item.apparel.lower()]}</span><br>\
#             </div></div><br><br>';
#             amount_total = int(amount_total) + int(priceMap[item.apparel.lower()])

#         message_body += f'\
#             <span><strong>Amount Total:</strong>$ {float(amount_total):.2f}</span><br>\
#         </div>'
        
#         # to_mail = os.environ.get("TO_EMAIL") if os.environ.get("TO_EMAIL") else "support@drophouse.art"
#         to_mail = "muthuselvam.m99@gmail.com"
#         email_service.send_email(
#             from_email='bucket@drophouse.art',
#             to_email=to_mail,
#             subject='Drophouse Order',
#             name=f"{order_model.shipping_info.firstName} {order_model.shipping_info.lastName}",
#             email="",
#             message_body=message_body
#         )

#         uid = order_model.user_id
#         items = order_model.item
#         await order_db_ops.update_order_status(uid, order_id, 'pending')

#         return {
#             "message": "Bulk order processed successfully",
#             "generated_data": generated_data,
#             "img": image_id
#         }

#     except HTTPException as http_ex:
#         raise http_ex
#     except Exception as e:
#         logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})


# # @bulk_order_router.post("/bulk-order")
# # async def make_bulk_order(request: BulkOrderRequest):
# #     print(type(request.prompts))

# #     if request.password != HARD_CODED_PASSWORD:
# #         raise HTTPException(status_code=403, detail="Invalid password")
    

# #     generated_data = await generate_prompts(request.prompts, request.numImages)
    
# #     image_id = await generate_images(generated_data)


# #     return {
# #         "message": "Bulk order processed successfully",
# #         "generated_data": generated_data,
# #         "img": image_id
# #     }
