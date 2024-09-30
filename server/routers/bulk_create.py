from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket
from models.bulkordermodel import BulkOrderRequest
from models.regeneratemodel import Regenerate
from models.reorder import Reorder
from models.OrderItemModel import OrderItem
from models.ShippingModel import ShippingModel
from models.ItemModel import ItemModel
from ai_models.utils import generate_prompts, generate_images, generate_three_images, generate_three_prompts
from routers.order_info import PlaceOrderDataRequest, place_order
from fastapi.responses import JSONResponse, FileResponse
from aws_utils import generate_presigned_url, processAndSaveImage
from inspect import currentframe, getframeinfo
from database.OrderOperations import OrderOperations
from database.UserOperations import UserOperations
from database.PricesOperations import PricesOperations
from database.OrganizationOperation import OrganizationOperation
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
from utils.printful_util import applyMask_and_removeBackground_file
from utils.generate_vector_ai import generate_zip_pre, generate_pdf_pre, clean_old_data_prepared
from PIL import Image
import requests
from io import BytesIO
import base64
import asyncio

bulk_order_router = APIRouter()
HARD_CODED_PASSWORD = "Drophouse23#"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ag_task_storage = {}
min_retry = 10

@bulk_order_router.post("/bulk-download-prepared_orders")
async def bulk_prepare(
    background_tasks: BackgroundTasks,
    order_ids: List[str],
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
    order_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
    org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation)),
):
    try:
        clear_old = await clean_old_data_prepared()
        # mask_image_path = "./images/masks/elephant_mask.png"
        result = await db_ops.get_student_order(order_ids)
        if result:
            for order in result:
                if "images" in order:
                    if 'org_id' not in order:
                        logger.error(f"Organization id not found in ORDER", exc_info=True)
                        continue
                        # raise HTTPException(
                        #     status_code=404,
                        #     detail={
                        #         "message": "Org Id not found",
                        #         "currentFrame": getframeinfo(currentframe()),
                        #     },
                        # )

                    organization = await org_db_ops.get_by_id(order['org_id'])
                    mask_data = process_mask_data(organization, False)

                    if not mask_data or mask_data == None:
                        mask_data = "pending"
                        for image in order['images']:
                            if 'greenmask' not in order['images'][image]:
                                mask_data = None
                                break
                            else:
                                if 'greenmask' in order['images'][image] and order['images'][image]['greenmask'] != 'null' and order['images'][image]['greenmask'] != '':
                                    order['images'][image]['greenmask'] = process_mask_data(order['images'][image]['greenmask'], True)
                                else:
                                    mask_data = None
                                    break
                    else:
                        for image in order['images']:
                            order['images'][image]['greenmask'] = mask_data
                    
                    if not mask_data or mask_data == None:
                        logger.error(f"Green mask not found in request", exc_info=True)
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "message": "Green mask not found",
                                "currentFrame": getframeinfo(currentframe()),
                            },
                        )
                        
                    for image in order["images"]:
                        size = image.split("_", 1)[0]
                        zip_folder1 = f"/mnt/data/student_module_zip_download1/temp_student_products/{size}"
                        if not os.path.exists(zip_folder1):
                            os.makedirs(zip_folder1)
                        image_path = f"{zip_folder1}/{image}.png"
                        image_data = applyMask_and_removeBackground_file(
                            order["images"][image]["img_path"],
                            order["images"][image]["greenmask"],
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

def strip_base64_prefix(base64_str):
    if base64_str.startswith('data:image/png;base64,'):
        return base64_str[len('data:image/png;base64,'):]
    return base64_str

def correct_base64_padding(base64_str):
    padding = len(base64_str) % 4
    if padding != 0:
        base64_str += '=' * (4 - padding)
    return base64_str

def percentage_to_pixels(percentage, total_pixels):
    return (percentage / 100) * total_pixels

async def get_selected_preview_image(pattern_src_url, default_product_base64, Dim_left, Dim_top, Dim_width, Dim_height):
    try:
        # logger.info(f"Calculated Coordinates - x: {tmp_x}, y: {tmp_y}, width: {tmp_width}, height: {tmp_height}")
        default_product_base64_new = correct_base64_padding(strip_base64_prefix(default_product_base64))
        cloth_img_data = base64.b64decode(default_product_base64_new)
        if pattern_src_url.startswith('data:image/jpeg;base64,'):
            pattern_img_res = correct_base64_padding(pattern_src_url[len('data:image/jpeg;base64,'):])
            pattern_img_respons = base64.b64decode(pattern_img_res)
            cloth_img = Image.open(BytesIO(cloth_img_data)).convert("RGBA")
            pattern_img = Image.open(BytesIO(pattern_img_respons)).convert("RGBA")
        elif pattern_src_url.startswith('data:image/png;base64,'):
            pattern_img_res = correct_base64_padding(pattern_src_url[len('data:image/png;base64,'):])
            pattern_img_respons = base64.b64decode(pattern_img_res)
            cloth_img = Image.open(BytesIO(cloth_img_data)).convert("RGBA")
            pattern_img = Image.open(BytesIO(pattern_img_respons)).convert("RGBA")
        else:
            pattern_img_response = requests.get(pattern_src_url)
            pattern_img_response.raise_for_status()
            cloth_img = Image.open(BytesIO(cloth_img_data)).convert("RGBA")
            pattern_img = Image.open(BytesIO(pattern_img_response.content)).convert("RGBA")
        total_pixels = cloth_img.height
        x = percentage_to_pixels(Dim_left, total_pixels)
        y = percentage_to_pixels(Dim_top, total_pixels)
        width = percentage_to_pixels(Dim_width, total_pixels)
        height = percentage_to_pixels(Dim_height, total_pixels)
        tmp_x = round(x)
        tmp_y = round(y)
        tmp_width = round(width)
        tmp_height = round(height)
        logger.info(f"Cloth image size: {cloth_img.size}, Pattern image size: {pattern_img.size}, Cloth image height: {cloth_img.height}")
        pattern_img = pattern_img.resize((tmp_height, tmp_width))  
        output_canvas = Image.new("RGBA", (total_pixels, total_pixels), (255, 255, 255, 0))
        output_canvas.paste(pattern_img, (tmp_x, tmp_y), pattern_img)
        output_canvas.paste(cloth_img, (0, 0), cloth_img)
        if (tmp_x < 0 or tmp_y < 0 or 
            tmp_x + tmp_width > total_pixels or 
            tmp_y + tmp_height > total_pixels):
            raise ValueError("Pattern image dimensions exceed canvas bounds")
        output_image = BytesIO()
        output_canvas.save(output_image, format="PNG")
        output_image.seek(0)
        base64_image = base64.b64encode(output_image.getvalue()).decode('utf-8')
        base64_url = f"data:image/png;base64,{base64_image}"

        return base64_url

    except Exception as e:
        logger.error(f"Error generating preview image: {e}")
        return None

@bulk_order_router.post("/generate_three_image")
async def generate_three_image(
    request: Regenerate,
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        image_count = 3
        generated_data = await generate_three_prompts(request.prompts, image_count)
        response_data = await generate_three_images(generated_data)
        img_urls = []
        prompts = []
        for idx in range(image_count):
            image_response = response_data[idx]
            img_url = image_response[1]
            img_prompts = image_response[2]
            prompts.append(img_prompts)
            img_urls.append(img_url)
        return {"data": img_urls,"prompt":prompts}
    except HTTPException as http_ex:
        raise http_ex
@bulk_order_router.post("/regenerate_order")
async def regenerate_order(
    request: Reorder,
    order_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
    price_db_ops: BaseDatabaseOperation = Depends(get_db_ops(PricesOperations)),
    org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation))
):
    try:
        user_data = request.file
        tasks = []
        for idx in range(len(user_data)):              
            order_id = str(uuid.uuid4())
            if 'order_id' in user_data[idx]:
                order_id = user_data[idx]['order_id']
                
            org_id = user_data[idx]['org_id']
            img_id = str(uuid.uuid4())
            # image_data = user_data[idx]['img_url']
            # base64Data = image_data[len('data:image/jpeg;base64,'):]
            # img_data = f"data:image/png;base64,{base64Data}"
            img_url = processAndSaveImage(user_data[idx]['img_url'], img_id, "browse-image-v2")
            organization = await org_db_ops.get_organization_data(org_id)
            if not organization:
                thumbnail = 'null'
            else:
                default_product = next(
                    (
                        product for product in organization['products']
                        if product['name'] == user_data[idx]['apparel'] and
                        isinstance(product['colors'], dict) and
                        any(color['name'] == user_data[idx]['color'] for color in product['colors'].values())
                    ),
                    None
                )
                if not default_product:
                    thumbnail = 'null'
                    logger.error(f"Default product not found for apparel: {user_data[idx]['apparel']} and color: {user_data[idx]['color']}")
                else:
                    color_asset = next(
                    (
                        color['asset']['front'] for color in default_product['colors'].values()
                        if color['name'] == user_data[idx]['color']
                    ),
                    None
                    )
                    if not color_asset:
                        thumbnail = 'null'
                        logger.error(f"Choosen color not found for apparel: {user_data[idx]['apparel']} and color: {user_data[idx]['color']}")
                    else:
                        Dim_left = default_product['dimensions']['left']
                        Dim_top = default_product['dimensions']['top']
                        Dim_width = default_product['dimensions']['width']
                        Dim_height = default_product['dimensions']['height']
                        thumbnail = await get_selected_preview_image(
                            pattern_src_url= user_data[idx]['img_url'],
                            default_product_base64=color_asset,
                            Dim_left=Dim_left,
                            Dim_top=Dim_top,
                            Dim_width=Dim_width,
                            Dim_height=Dim_height
                        )
                        thumbnail_img_id = "t_" + img_id
                        tasks.append(asyncio.to_thread(processAndSaveImage, thumbnail, thumbnail_img_id, "thumbnails-cart"))


            order_model = OrderItem(
                user_id=user_data[idx]['email'],
                org_id=org_id,
                org_name=user_data[idx]['org_name'],
                autogenerated=True,
                order_id=order_id,
                status='pending',
                timestamp=datetime.datetime.utcnow(),
                shipping_info=ShippingModel(
                    firstName=user_data[idx]['first_name'],
                    lastName=user_data[idx]['last_name'],
                    email=user_data[idx]['email'],
                    phone=user_data[idx]['phone'],
                    streetAddress=user_data[idx]['streetAddress'],
                    streetAddress2=user_data[idx]['streetAddress2'],
                    city=user_data[idx]['city'],
                    stateProvince=user_data[idx]['state'],
                    postalZipcode=user_data[idx]['postalZipcode'],
                    addressType='primary'
                ),
                item=[ItemModel(
                    apparel=user_data[idx]['apparel'],
                    size=user_data[idx]['shirt-size'],
                    color=user_data[idx]['color'],
                    img_id=img_id,
                    prompt=user_data[idx]['prompt'],
                    timestamp=datetime.datetime.utcnow(),
                    thumbnail=thumbnail,
                    toggled=user_data[idx]['toggled'],
                    price=user_data[idx]['price']
                )]
            )

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
        await asyncio.gather(*tasks)
        return user_data
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
    org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation))
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        ag_task_storage[request.task_id] = {
            'success': 0,
            'failed': 0,
            'progress': 0,
            'total': request.numImages
        }
        semaphore = asyncio.Semaphore(100)
        retry_limit = max(len(request.file) // 2, min_retry)
        if not request.is_prompt and not request.is_toggled:
            generated_data = await generate_prompts(request.prompts, request.numImages)
            print('analysis of prompt data', len(request.file), len(generated_data))
            response_data = await generate_images(generated_data,semaphore)
            print('analysis of image data', len(request.file), len(response_data))
        elif request.is_prompt and not request.is_toggled:
            response_data = await generate_images(request.prompts,semaphore)
        elif request.is_toggled:
            pass

        retry = 0
        tasks = []
        file_data = request.file
        # retry_limit = int(len(user_data)/2) if int(len(user_data)/2) > min_retry else min_retry
        for idx in range(len(request.file)):
            user_data = request.file[idx]
            if not request.is_toggled:
                imageresponse = response_data[idx]
                if isinstance(imageresponse, Exception) or imageresponse is None:
                    if retry > retry_limit:
                        raise HTTPException(status_code=400, detail={'message': "Image regeneration thershold reached", 'currentFrame': getframeinfo(currentframe())})
                    logger.info(f"Image Generation failed : retrying [{retry}/{retry_limit}]")
                    imageresponse, retry = await generate_failed_image(request.prompts, retry, retry_limit, semaphore)
                    
                order_id = str(uuid.uuid4())
                if 'order_id' in user_data:
                    order_id = user_data['order_id']

                org_id = user_data['org_id']
                organization = await org_db_ops.get_organization_data(org_id)
                if not organization:
                    thumbnail = 'null'
                else:
                    default_product = next(
                        (
                            product for product in organization['products']
                            if product['name'] == user_data['apparel'] and
                            isinstance(product['colors'], dict) and
                            any(color['name'] == user_data['color'] for color in product['colors'].values())
                        ),
                        None
                    )
                    if not default_product:
                        thumbnail = 'null'
                        logger.error(f"Default product not found for apparel: {user_data['apparel']} and color: {user_data['color']}")
                        # raise HTTPException(status_code=404, detail=f"Default product not found for apparel: {user_data[idx]['apparel']} and color: {user_data[idx]['color']}")
                    else:
                        color_asset = next(
                        (
                            color['asset']['front'] for color in default_product['colors'].values()
                            if color['name'] == user_data['color']
                        ),
                        None
                        )
                        if not color_asset:
                            thumbnail = 'null'
                            logger.error(f"Choosen color not found for apparel: {user_data['apparel']} and color: {user_data['color']}")
                            # raise HTTPException(status_code=404, detail=f"Asset not found for color: {user_data[idx]['color']}")
                        else:
                            Dim_left = default_product['dimensions']['left']
                            Dim_top = default_product['dimensions']['top']
                            Dim_width = default_product['dimensions']['width']
                            Dim_height = default_product['dimensions']['height']
                            thumbnail = await get_selected_preview_image(
                                pattern_src_url= generate_presigned_url(imageresponse[1], "browse-image-v2"),
                                default_product_base64=color_asset,
                                Dim_left=Dim_left,
                                Dim_top=Dim_top,
                                Dim_width=Dim_width,
                                Dim_height=Dim_height
                            )
                            thumbnail_img_id = "t_" + imageresponse[1]
                            tasks.append(asyncio.to_thread(processAndSaveImage, thumbnail, thumbnail_img_id, "thumbnails-cart"))


                order_model = OrderItem(
                    user_id=user_data['email'],
                    org_id=org_id,
                    org_name=user_data['org_name'],
                    autogenerated=True,
                    order_id=order_id,
                    status='pending',
                    timestamp=datetime.datetime.utcnow(),
                    shipping_info=ShippingModel(
                        firstName=user_data['first_name'],
                        lastName=user_data['last_name'],
                        email=user_data['email'],
                        phone=user_data['phone'],
                        streetAddress=user_data['streetAddress'],
                        streetAddress2=user_data['streetAddress2'],
                        city=user_data['city'],
                        stateProvince=user_data['state'],
                        postalZipcode=user_data['postalZipcode'],
                        addressType='primary'
                    ),
                    item=[ItemModel(
                        apparel=user_data['apparel'],
                        size=user_data['shirt-size'],
                        color=user_data['color'],
                        img_id=imageresponse[1],
                        prompt=imageresponse[2],
                        timestamp=datetime.datetime.utcnow(),
                        thumbnail=thumbnail,
                        toggled=user_data['toggled'],
                        price=user_data['price']
                    )]
                )
                file_data[idx]['img_id'] = imageresponse[1]
                file_data[idx]['prompt'] = imageresponse[2]

                if 'order_id' in user_data:
                    result = await order_db_ops.update_order(order_model)
                    if not result:
                        raise HTTPException(status_code=404, detail={'message': "Can't able to update an order", 'currentFrame': getframeinfo(currentframe())})
                    ag_task_storage[request.task_id]['success'] = ag_task_storage[request.task_id]['success'] + 1
                else:
                    result = await order_db_ops.create_order(order_model)
                    if result:
                        file_data[idx]['order_id'] = order_id
                        ag_task_storage[request.task_id]['success'] = ag_task_storage[request.task_id]['success'] + 1
                    else:
                        ag_task_storage[request.task_id]['failed'] = ag_task_storage[request.task_id]['failed'] + 1
                        raise HTTPException(status_code=404, detail={'message': "Can't able to create an order", 'currentFrame': getframeinfo(currentframe())})
            else:                 
                order_id = str(uuid.uuid4())
                if 'order_id' in user_data:
                    order_id = user_data['order_id']

                org_id = user_data['org_id']
                organization = await org_db_ops.get_organization_data(org_id)
                if not organization:
                    thumbnail = 'null'
                else:
                    default_product = next(
                        (
                            product for product in organization['products']
                            if product['name'] == user_data['apparel'] and
                            isinstance(product['colors'], dict) and
                            any(color['name'] == user_data['color'] for color in product['colors'].values())
                        ),
                        None
                    )
                    if not default_product:
                        thumbnail = 'null'
                        logger.error(f"Default product not found for apparel: {user_data['apparel']} and color: {user_data['color']}")
                        # raise HTTPException(status_code=404, detail=f"Default product not found for apparel: {user_data[idx]['apparel']} and color: {user_data[idx]['color']}")
                    else:
                        color_asset = next(
                        (
                            color['asset']['front'] for color in default_product['colors'].values()
                            if color['name'] == user_data['color']
                        ),
                        None
                        )
                        if not color_asset:
                            thumbnail = 'null'
                            logger.error(f"Choosen color not found for apparel: {user_data['apparel']} and color: {user_data['color']}")
                            # raise HTTPException(status_code=404, detail=f"Asset not found for color: {user_data[idx]['color']}")
                        else:
                            Dim_left = default_product['dimensions']['left']
                            Dim_top = default_product['dimensions']['top']
                            Dim_width = default_product['dimensions']['width']
                            Dim_height = default_product['dimensions']['height']
                            thumbnail = await get_selected_preview_image(
                                pattern_src_url= user_data['toggled'],
                                default_product_base64=color_asset,
                                Dim_left=Dim_left,
                                Dim_top=Dim_top,
                                Dim_width=Dim_width,
                                Dim_height=Dim_height
                            )
                            thumbnail_img_id = "t_" + user_data['img_id']
                            tasks.append(asyncio.to_thread(processAndSaveImage, thumbnail, thumbnail_img_id, "thumbnails-cart"))


                order_model = OrderItem(
                    user_id=user_data['email'],
                    org_id=org_id,
                    org_name=user_data['org_name'],
                    autogenerated=True,
                    order_id=order_id,
                    status='pending',
                    timestamp=datetime.datetime.utcnow(),
                    shipping_info=ShippingModel(
                        firstName=user_data['first_name'],
                        lastName=user_data['last_name'],
                        email=user_data['email'],
                        phone=user_data['phone'],
                        streetAddress=user_data['streetAddress'],
                        streetAddress2=user_data['streetAddress2'],
                        city=user_data['city'],
                        stateProvince=user_data['state'],
                        postalZipcode=user_data['postalZipcode'],
                        addressType='primary'
                    ),
                    item=[ItemModel(
                        apparel=user_data['apparel'],
                        size=user_data['shirt-size'],
                        color=user_data['color'],
                        img_id=user_data['img_id'],
                        prompt=user_data['prompt'],
                        timestamp=datetime.datetime.utcnow(),
                        thumbnail=thumbnail,
                        toggled=user_data['toggled'],
                        price=user_data['price']
                    )]
                )

                if 'order_id' in user_data:
                    result = await order_db_ops.update_order(order_model)
                    if not result:
                        raise HTTPException(status_code=404, detail={'message': "Can't able to update an order", 'currentFrame': getframeinfo(currentframe())})
                    ag_task_storage[request.task_id]['success'] = ag_task_storage[request.task_id]['success'] + 1
                else:
                    result = await order_db_ops.create_order(order_model)
                    if result:
                        file_data[idx]['order_id'] = order_id
                        ag_task_storage[request.task_id]['success'] = ag_task_storage[request.task_id]['success'] + 1
                    else:
                        ag_task_storage[request.task_id]['failed'] = ag_task_storage[request.task_id]['success'] + 1
                        raise HTTPException(status_code=404, detail={'message': "Can't able to create an order", 'currentFrame': getframeinfo(currentframe())})
        await asyncio.gather(*tasks)
        ag_task_storage.pop(request.task_id, None)
        return file_data
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

async def generate_failed_image(prompts: List[str], retry: int, retry_limit: int, semaphore: asyncio.Semaphore):
    try:
        retry += 1
        logger.info(f"Image Generation failed : retrying begin [{retry}/{retry_limit}]")
        generated_data = await generate_prompts([random.choice(prompts)], 1)
        response_data = await generate_images(generated_data,semaphore)

        imageresponse = response_data[0]
        if isinstance(imageresponse, Exception) or imageresponse is None:
            logger.info(f"Image Generation failed : retrying failed [{retry-1}/{retry_limit}]")
            if retry > retry_limit:
                raise HTTPException(status_code=400, detail={'message': "Image regeneration threshold reached", 'currentFrame': getframeinfo(currentframe())})
            return await generate_failed_image(prompts, retry, retry_limit,semaphore)

        logger.info(f"Image Generation failed : retrying success")
        return imageresponse, retry
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in bulk order session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={'message': "Internal Server Error", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})

@bulk_order_router.websocket("/ws/progress/autogenerate/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            if task_id in ag_task_storage:
                await websocket.send_json(ag_task_storage[task_id])
            else:
                break
            await asyncio.sleep(5)
    except Exception as e:
        logger.info(f"WebSocket error: {e}")
    finally:
        await websocket.close()

def process_mask_data(organization, isImgId):
    if not organization:
        return None

    if not isImgId:
        if 'greenmask' in organization and organization['greenmask'] != 'null' and organization['greenmask'] != '':
            mask_data = organization['greenmask']
        else:
            return None
    else:
        if organization != None and organization != "":
            mask_data = organization
        else:
            return None
    
    if isinstance(mask_data, bytes) and mask_data.startswith(b'data:image'):
        mask_data = mask_data.split(b',')[1]
    else:
        try:
            if not mask_data or mask_data == None:
                return None

            mask_data = generate_presigned_url(mask_data, "drophouse-skeleton")
            response = requests.get(mask_data)
            if response.status_code == 200:
                mask_data = base64.b64encode(response.content)
            else:
                raise ValueError(f"Error downloading image. Status code: {response.status_code}")
        except Exception as e:
            logger.info(f"Error processing mask data: {e}")
            mask_data = None

    return mask_data