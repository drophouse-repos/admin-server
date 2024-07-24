import os
import logging
import requests
import traceback
from db import get_db_ops
from bson import json_util
from fastapi import Depends
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from fastapi.responses import JSONResponse, FileResponse
from inspect import currentframe, getframeinfo
from database.BASE import BaseDatabaseOperation
from fastapi import APIRouter, Body, HTTPException, BackgroundTasks
from database.UserOperations import UserOperations
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


@admin_dashboard_router.get("/admin_orders")
async def get_admin_orders(
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    try:
        result = await db_ops.get()
        return JSONResponse(content=json_util.dumps(result))
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


@admin_dashboard_router.post("/print_order")
async def print_order(
    order_info: OrderItem,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    try:
        printful_mapping = products_and_variants_map()

        mask_image_path = "./images/masks/rh_mask.png"
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
            if item.apparel in printful_mapping:
                product = printful_mapping[item.apparel]
            elif item.apparel + "_" + item.color in printful_mapping:
                product = printful_mapping[item.apparel + "_" + item.color]
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
                if item.color in product["variants"][size]:
                    variant_id = product["variants"][size][item.color]
                elif item.color in product["color_map"]:
                    color = product["color_map"][item.color]
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

            image_url = (
                item.toggled
                if item.toggled
                else generate_presigned_url(item.img_id, "browse-image-v2")
            )
            image_data = applyMask_and_removeBackground(
                image_url, mask_image_path, item.img_id
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
                    item_data["files"][0]["position"]["width"] = 512
                    item_data["files"][0]["position"]["height"] = 512
                    item_data["files"][0]["position"]["left"] = 375
                    item_data["files"][0]["position"]["top"] = 325

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
        is_updated = await db_ops.update(order_info["user_id"], order_info["order_id"], "prepared")
        if is_updated:
            logger.info(f"Status updated /printful: {image}")
        else:
            logger.error(f"Not able to update status /printful, Error: {image}")

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

class DownloadRequest(BaseModel):
    password: str
    mode: str
    order_ids: List[str]

HARD_CODED_PASSWORD = 'Drophouse23#'
@admin_dashboard_router.post("/download_student_verified_orders")
async def download_student_verified_orders(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    db_ops: BaseDatabaseOperation = Depends(get_db_ops(UserOperations)),
):
    if request.password != HARD_CODED_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    try:
        clear_old = await clean_old_data()
        mask_image_path = "./images/masks/elephant_mask.png"
        result = await db_ops.get_student_order(request.order_ids)
        if result:
            for order in result:
                if "images" in order:
                    for image in order["images"]:
                        image_data = applyMask_and_removeBackground(
                            order["images"][image]["img_path"],
                            mask_image_path,
                            order["images"][image]["img_id"],
                        )
                        result = generate_vector_image(image_data, image, request.mode)
                        if result:
                            logger.info(f"Vector Generated : {image}")
                            is_updated = await db_ops.update(order["user_id"], order["order_id"], "prepared")
                            if is_updated:
                                logger.info(f"Status updated : {image}")
                            else:
                                logger.error(f"Not able to update status, Error: {image}")
                        else:
                            logger.error(f"Vector Error: {image}")

            zip_path = await generate_zip(background_tasks)
            if not os.path.exists(zip_path):
                return JSONResponse(
                    content=json_util.dumps({"error": f"File not found: {zip_path}"})
                )

            return FileResponse(zip_path, filename=f"student_products.zip")
        else:
            result = []
            return JSONResponse(content=json_util.dumps(result))
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(
            f"Error in download_student_verified_orders: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )
