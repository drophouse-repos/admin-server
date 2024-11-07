import os
import logging
import requests
import asyncio
import traceback
import base64
from db import get_db_ops
from bson import json_util
from fastapi import Depends
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from fastapi.responses import JSONResponse, FileResponse
from inspect import currentframe, getframeinfo
from database.BASE import BaseDatabaseOperation
from database.OrganizationOperation import OrganizationOperation
from fastapi import APIRouter, Body, HTTPException, BackgroundTasks, WebSocket
from database.UserOperations import UserOperations
from database.OrderOperations import OrderOperations
from email_service.EmailService import EmailService
from models.OrderItemModel import OrderItem
from aws_utils import generate_presigned_url
from utils.printful_util import (
    applyMask_and_removeBackground,
    printful_request,
    products_and_variants_map,
)
from utils.generate_vector_ai import (
    generate_vector_image,
    generate_zip,
    generate_pdf,
    clean_old_data,
    convert_eps_to_base64,
)

allowedUsers = [
    "trilokshan@drophouse.ai",
    "kush@drophouse.ai",
    "balapradeepbala@gmail.com",
    "muthuselvam.m99@gmail.com",
]

email_service = EmailService()
HARD_CODED_PASSWORD = 'Drophouse23#'
vector_task_storage = {}
class DeleteRequest(BaseModel):
    user_id: str
    order_id: str

class DownloadRequest(BaseModel):
    password: str
    mode: str
    order_ids: list[str]
    task_id: str

class EmailRequest(BaseModel):
    to_mail: str
    subject: str
    content: str

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
admin_dashboard_router = APIRouter()


@admin_dashboard_router.get("/admin_users")
async def get_admin_orders():
    try:
        if allowedUsers:
            return allowedUsers
        else:
            return []
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in get_admin_orders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )


class OrderIdsRequest(BaseModel):
    order_ids: List[str]

@admin_dashboard_router.post("/get_toggled_url")
async def get_toggled_url(
    request: OrderIdsRequest,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
):
    try:
        results = []
        for order_id in request.order_ids:
            result = await db_ops.get_toggled_url(order_id)
            results.append(result)
        return JSONResponse(content=json_util.dumps(results))
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in get_admin_orders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

@admin_dashboard_router.post("/admin_orders")
async def get_admin_orders(
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    try:
        result = await db_ops.get_v2()
        # return JSONResponse(content=json_util.dumps(result))
        return JSONResponse(content=result)
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in get_admin_orders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

@admin_dashboard_router.post("/delete_order")
async def delete_order(
    order_info: DeleteRequest,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrderOperations)),
):
    try:
        result = await db_ops.delete_order(order_info.order_id)
        if result:
            return JSONResponse(content=json_util.dumps({"message": "Order deleted successfully"}))
        else:
            raise HTTPException(
                status_code=404,
                detail={"message": "Order not found or no update needed","currentFrame": getframeinfo(currentframe())},
            )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in update_order_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal Server Error","currentFrame": getframeinfo(currentframe()),"detail": str(traceback.format_exc())}
        )

@admin_dashboard_router.post("/update_order_status")
async def update_order_status(
    email_data: EmailRequest,
    user_id: str = Body(..., embed=True),
    order_id: str = Body(..., embed=True),
    new_status: str = Body(..., embed=True),
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    try:
        result = await db_ops.update(user_id, order_id, new_status)
        if result:
            if new_status == "cancelled":
                email_service.send_email(
                    from_email="bucket@drophouse.art",
                    to_email=email_data.to_mail,
                    subject=email_data.subject,
                    name=user_id,
                    email=email_data.to_mail,
                    message_body=email_data.content,
                )
            return JSONResponse(
                content=json_util.dumps({"message": "Order updated successfully"})
            )
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Order not found or no update needed",
                    "currentFrame": getframeinfo(currentframe()),
                },
            )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in update_order_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

class OrderUpdate(BaseModel):
    email_data: EmailRequest
    user_id: str
    order_id: str
    new_status: str

@admin_dashboard_router.post("/update_bulk_order_status")
async def update_bulk_order_status(
    updates: List[OrderUpdate] = Body(...),
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    try:
        # Prepare a list of bulk update requests
        bulk_updates = [
            {"user_id": update.user_id, "order_id": update.order_id, "new_status": update.new_status}
            for update in updates
        ]

        # Perform the bulk update
        result = await db_ops.bulk_update_orders(bulk_updates)

        if result:
            # Send emails for each update if status is "cancelled"
            for update in updates:
                if update.new_status == "cancelled":
                    email_service.send_email(
                        from_email="bucket@drophouse.art",
                        to_email=update.email_data.to_mail,
                        subject=update.email_data.subject,
                        name=update.user_id,
                        email=update.email_data.to_mail,
                        message_body=update.email_data.content,
                    )
            return JSONResponse(
                content=json_util.dumps({"message": "Orders updated successfully"})
            )
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "No orders updated",
                    "currentFrame": getframeinfo(currentframe()),
                },
            )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in update_order_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )
    

@admin_dashboard_router.post("/print_order")
async def print_order(
    order_info: OrderItem,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
    org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation)),
):
    try:
        printful_mapping = products_and_variants_map()
        if not hasattr(order_info, 'org_id'):
            logger.error(f"Organization id not found in request", exc_info=True)
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Org Id not found",
                    "currentFrame": getframeinfo(currentframe()),
                },
            )

        organization = await org_db_ops.get_by_id(order_info.org_id)
        mask_data = process_mask_data(organization, False)

        if not mask_data or mask_data == None:
            mask_data = "pending"
            for item in order_info.item:
                if not hasattr(item, 'greenmask'):
                    mask_data = None
                    break
                else:
                    if hasattr(item, 'greenmask') and item.greenmask != 'null' and item.greenmask != '':
                        item.greenmask = process_mask_data(item.greenmask, True)
                    else:
                        mask_data = None
                        break
        else:
            for item in order_info.item:
                item.greenmask = mask_data
        
        if not mask_data or mask_data == None:
            logger.error(f"Green mask not found in request", exc_info=True)
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Green mask not found",
                    "currentFrame": getframeinfo(currentframe()),
                },
            )

        shipping_info = order_info.shipping_info
        order_data = {
            "recipient": {
                "name": shipping_info.firstName + " " + shipping_info.lastName,
                "address1": shipping_info.streetAddress,
                "city": shipping_info.city,
                "state_code": shipping_info.stateProvince,
                "country_code": "US",
                "zip": shipping_info.postalZipcode,
            },
            "items": [],
        }

        items = order_info.item
        for item in items:
            product = {}
            # print(item.apparel, item.apparel + "_" + item.color, printful_mapping)
            if item.apparel in printful_mapping:
                product = printful_mapping[item.apparel]
            elif item.apparel + "_" + item.color.lower() in printful_mapping:
                product = printful_mapping[item.apparel + "_" + item.color.lower()]
            else:
                logger.error(f"Product not found in printful", exc_info=True)
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Product not found",
                        "currentFrame": getframeinfo(currentframe()),
                    },
                )

            size = item.size
            if item.size in product["size_map"]:
                size = product["size_map"][item.size]

            if size not in product["size"]:
                logger.error(f"Size not found for this product", exc_info=True)
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Size not found for this product",
                        "currentFrame": getframeinfo(currentframe()),
                    },
                )

            variant_id = ""
            color = item.color
            if size in product["variants"]:
                # print(item.color, product["variants"][size], product['color_map'])
                if item.color in product["variants"][size]:
                    variant_id = product["variants"][size][item.color.lower()]
                elif item.color.lower() in product["color_map"]:
                    color = product["color_map"][item.color.lower()]
                    if color in product["variants"][size]:
                        variant_id = product["variants"][size][color]
                else:
                    logger.error(f"Color not found for this product", exc_info=True)
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "message": "Color not found for this product",
                            "currentFrame": getframeinfo(currentframe()),
                        },
                    )
            else:
                logger.error(
                    f"Size not found for this product inside variants", exc_info=True
                )
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Size not found for this product inside variants",
                        "currentFrame": getframeinfo(currentframe()),
                    },
                )

            if not variant_id:
                logger.error(f"Variant_id not found for this product", exc_info=True)
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Size not found for this product inside variants",
                        "currentFrame": getframeinfo(currentframe()),
                    },
                )

            print('item.toggled check', 'picking toggled url' if item.toggled else 'picking generated url')
            image_url = (
                item.toggled
                if item.toggled
                else generate_presigned_url(item.img_id, "browse-image-v2")
            )
            print('image url -> ', image_url)
            image_data = await applyMask_and_removeBackground(
                image_url, item.greenmask, item.img_id
            )

            item_data = {
                "variant_id": variant_id,
                "quantity": 1,
                "files": [
                    {
                        "url": image_data,
                    }
                ],
            }
            if "files" in item_data and item_data["files"][0]:
                if item.apparel == "hoodie" or item.apparel == "tshirt":
                    item_data["files"][0]["type"] = "front"
                    item_data["files"][0]["position"] = {}
                elif item.apparel == "cap":
                    # default, embroidery_front, embroidery_front_large, embroidery_back, embroidery_left, embroidery_right, mockup
                    item_data["files"][0]["type"] = "embroidery_front"
                    item_data["files"][0]["position"] = {}
                elif item.apparel == "mug":
                    pass

            if (
                "files" in item_data
                and item_data["files"][0]
                and "position" in item_data["files"][0]
            ):
                item_data["files"][0]["position"]["top"] = 0
                item_data["files"][0]["position"]["left"] = 0
                item_data["files"][0]["position"]["limit_to_print_area"] = True

                if item.apparel == "hoodie":
                    item_data["files"][0]["position"]["area_width"] = 1024
                    item_data["files"][0]["position"]["area_height"] = 1024
                    item_data["files"][0]["position"]["width"] = 256
                    item_data["files"][0]["position"]["height"] = 256
                    item_data["files"][0]["position"]["left"] = 390
                    item_data["files"][0]["position"]["top"] = 270
                    # item_data["files"][0]["position"]["area_width"] = 512
                    # item_data["files"][0]["position"]["area_height"] = 512
                    # item_data["files"][0]["position"]["width"] = 256
                    # item_data["files"][0]["position"]["height"] = 256
                    # item_data["files"][0]["position"]["left"] = 125
                    # item_data["files"][0]["position"]["top"] = 125

                if item.apparel == "tshirt":
                    item_data["files"][0]["position"]["width"] = 1024
                    item_data["files"][0]["position"]["height"] = 1024
                    item_data["files"][0]["position"]["left"] = 375
                    item_data["files"][0]["position"]["top"] = 325

                if item.apparel == "cap":
                    item_data["files"][0]["position"]["width"] = 512
                    item_data["files"][0]["position"]["height"] = 512
                    item_data["files"][0]["position"]["left"] = 325

                if item.apparel == "mug":
                    item_data["files"][0]["position"]["width"] = 512
                    item_data["files"][0]["position"]["height"] = 512

            if item.apparel == "cap":
                item_data["files"][0]["options"] = [
                    {"id": "full_color", "value": "true"}
                ]
            elif item.apparel == "tshirt" or item.apparel == "hoodie":
                item_data["options"] = {"stitch_color": color}
            order_data["items"].append(item_data)

        print(order_data)
        endpoint = "/orders"
        response = printful_request(endpoint, method="POST", data=order_data)
        if response:
            is_updated = await db_ops.update(order_info.user_id, order_info.order_id, "draft")
            if is_updated:
                logger.info(f"Status updated /printful order_id: {order_info.order_id}")
            else:
                logger.error(f"Not able to update status /printful order_id, Error: {order_info.order_id}")

        return JSONResponse(
            content=json_util.dumps({"message": "Order added to printful"})
        )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in update_order_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )


@admin_dashboard_router.get("/get_products")
async def get_products():
    response = printful_request("/store/products")
    return JSONResponse(content=response)


@admin_dashboard_router.get("/get_variants")
async def get_variants(product_id):
    response = printful_request(f"/store/products/{product_id}")
    return JSONResponse(content=response)


@admin_dashboard_router.get("/get_product_map")
async def get_products_and_variants_map():
    return products_and_variants_map()

@admin_dashboard_router.post("/download_student_verified_orders")
async def download_student_verified_orders(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
    org_db_ops: BaseDatabaseOperation = Depends(get_db_ops(OrganizationOperation)),
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        await clean_old_data()
        vector_task_storage[request.task_id] = {
            'success': 0,
            'failed': 0,
            'progress': 0,
            'total': len(request.order_ids)
        }
        result = await db_ops.get_student_order(request.order_ids)
        if result:
            tasks = []
            for order in result:
                if "images" in order:
                    if 'org_id' not in order:
                        logger.error(f"Organization id not found in ORDER", exc_info=True)
                        vector_task_storage.pop(request.task_id, None)
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "message": "Org Id not found",
                                "currentFrame": getframeinfo(currentframe()),
                            },
                        )

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
                        vector_task_storage.pop(request.task_id, None)
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "message": "Green mask not found",
                                "currentFrame": getframeinfo(currentframe()),
                            },
                        )
                    
                    for image in order["images"]:
                        tasks.append(process_image(image, order['images'][image]['greenmask'], order, request.mode, db_ops, request.task_id))
            
            await asyncio.gather(*tasks, return_exceptions=True)

            zip_path = await generate_zip(background_tasks)  # Generate folder as zip and download
            if not os.path.exists(zip_path):
                vector_task_storage.pop(request.task_id, None)
                return JSONResponse(
                    content={"error": f"File not found: {zip_path}"}
                )

            vector_task_storage.pop(request.task_id, None)
            return FileResponse(zip_path, filename="student_products.zip")
        else:
            vector_task_storage.pop(request.task_id, None)
            return JSONResponse(content=[])
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error in download_student_verified_orders: {str(e)}", exc_info=True)
        # vector_task_storage.pop(request.task_id, None)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

semaphore = asyncio.Semaphore(100)  # Limit to 100 concurrent tasks
async def process_image(image, mask_data, order, mode, db_ops, task_id):
    async with semaphore:
        try:
            image_data = await applyMask_and_removeBackground(
                order["images"][image]["img_path"],
                mask_data,
                order["images"][image]["img_id"],
            )
            result = await generate_vector_image(image_data, image, mode)
            if result:
                logger.info(f"Vector Generated: {image}")
                vector_task_storage[task_id]['success'] = vector_task_storage[task_id]['success'] + 1
                if mode == 'production':  # Update order status
                    is_updated = await db_ops.update(order["user_id"], order["order_id"], "prepared")
                    if is_updated:
                        logger.info(f"Status updated: {image}")
                    else:
                        logger.error(f"Not able to update status, Error: {image}")
            else:
                vector_task_storage[task_id]['failed'] = vector_task_storage[task_id]['failed'] + 1
                logger.error(f"Vector Error: {image}")
        except Exception as e:
            vector_task_storage[task_id]['failed'] = vector_task_storage[task_id]['failed'] + 1
            logger.error(f"Error processing image {image}: {str(e)}", exc_info=True)

@admin_dashboard_router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            if task_id in vector_task_storage:
                await websocket.send_json(vector_task_storage[task_id])
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