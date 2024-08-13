from inspect import currentframe, getframeinfo
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from fastapi import HTTPException, BackgroundTasks
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import traceback
import requests
import aiofiles
import logging
import asyncio
import shutil
import base64
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

VECTORIZER_MODE = os.environ.get("VECTORIZER_MODE")
VECTORIZER_SECRET = os.environ.get("VECTORIZER_SECRET")
VECTORIZER_TOKEN = os.environ.get("VECTORIZER_PRIVATE_TOKEN")

if VECTORIZER_MODE == 'prod':
    VECTORIZER_MODE = 'production'

zip_folder = "/mnt/data/student_module_zip_download"
zip_folder1 = "/mnt/data/student_module_zip_download1"
output_folder = "/mnt/data/student_module_zip_download/zip"
output_folder1 = "/mnt/data/student_module_zip_download1/zip"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
if not os.path.exists(output_folder1):
    os.makedirs(output_folder1)

def convert_eps_to_base64(eps_path):
    try:
        logger.info(f"Received eps_path: {eps_path}")

        if not os.path.exists(eps_path):
            logger.error(f"Error in convert_eps_to_base64: File not found: {eps_path}")
            return JSONResponse(
                content=json.dumps({"error": f"File not found: {eps_path}"})
            )

        logger.info(f"File exists: {eps_path}")

        with Image.open(eps_path) as img:
            img = img.convert("RGB")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        return img_base64
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in convert_eps_to_base64: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def clean_old_data_prepared():
    try:
        if not os.path.exists(zip_folder1):
            os.makedirs(zip_folder1)

        zip_file = f"{zip_folder1}/temp_student_products"
        if os.path.exists(zip_file + ".zip"):
            os.remove(zip_file + ".zip")

        shutil.rmtree(zip_folder1)
        if not os.path.exists(output_folder1):
            os.makedirs(output_folder1)
        return "removed"
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in clean_old_data : {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def clean_old_data():
    try:
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)

        zip_file = f"{zip_folder}/temp_student_products.zip"
        if os.path.exists(zip_file):
            os.remove(zip_file)

        if os.path.exists(output_folder):
            shutil.rmtree(output_folder)
        os.makedirs(output_folder)

        return "removed"
    except Exception as error:
        logger.error(f"Error in clean_old_data: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def generate_vector_image(image_url, file_name, mode):
    retry_attempts = 3
    timeout_seconds = 60  # Increase timeout in seconds

    for attempt in range(retry_attempts):
        try:
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://vectorizer.ai/api/v1/vectorize",
                    data={
                        "mode": mode,
                        "image.url": image_url,
                        "output.file_format": "eps",
                    },
                    auth=(VECTORIZER_TOKEN, VECTORIZER_SECRET),
                    timeout=timeout_seconds,
                )

                size = file_name.split("_", 1)[0]
                if not os.path.exists(f"{output_folder}/{size}"):
                    os.makedirs(f"{output_folder}/{size}")

                if response.status_code == httpx.codes.OK:
                    file_path = f"{output_folder}/{size}/{file_name}.eps"
                    async with aiofiles.open(file_path, "wb") as out_file:
                        await out_file.write(response.content)
                    return file_path
                else:
                    logger.error(f"Error: {response.status_code} {response.text}")
                    return False

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.error(f"Attempt {attempt + 1} failed: {exc}")
            if attempt == retry_attempts - 1:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Vectorization request failed after multiple attempts",
                        "currentFrame": getframeinfo(currentframe()),
                        "detail": str(traceback.format_exc()),
                    },
                )
        except Exception as error:
            logger.error(f"Error in generate_vector_image: {error}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal Server Error",
                    "currentFrame": getframeinfo(currentframe()),
                    "detail": str(traceback.format_exc()),
                },
            )

async def generate_zip(background_tasks):
    try:
        zip_file = f"{zip_folder}/temp_student_products"
        shutil.make_archive(zip_file, "zip", output_folder)

        # Schedule clean-up tasks
        background_tasks.add_task(os.remove, zip_file + ".zip")
        background_tasks.add_task(shutil.rmtree, zip_folder)
        return f"{zip_file}.zip"
    except Exception as error:
        logger.error(f"Error in generate_zip: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def generate_zip_pre(background_tasks):
    try:
        zip_file = f"{zip_folder1}/temp_student_products"
        result = shutil.make_archive(zip_file, "zip", output_folder1)

        background_tasks.add_task(os.remove, zip_file + ".zip")
        background_tasks.add_task(shutil.rmtree, zip_folder1)
        return f"{zip_file}.zip"
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in generate zip : {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def generate_pdf(background_tasks):
    try:
        pdf_file = f"{zip_folder}/temp_student_products"
        folder_path = output_folder
        image_files = [
            f
            for f in os.listdir(folder_path)
            if f.lower().endswith(("png", "jpg", "jpeg", "eps"))
        ]
        image_files.sort()

        if not image_files:
            return f"{pdf_file}.pdf"

        c = canvas.Canvas(f"{pdf_file}.pdf", pagesize=letter)
        page_width, page_height = letter
        for image_file in image_files:
            image_path = os.path.join(folder_path, image_file)
            img = Image.open(image_path)
            img_width, img_height = img.size

            aspect_ratio = img_width / float(img_height)
            if aspect_ratio > 1:
                new_width = min(page_width, img_width)
                new_height = new_width / aspect_ratio
            else:
                new_height = min(page_height, img_height)
                new_width = new_height * aspect_ratio

            x_offset = (page_width - new_width) / 2
            y_offset = (page_height - new_height) / 2

            c.drawImage(
                ImageReader(img), x_offset, y_offset, width=new_width, height=new_height
            )
            c.showPage()

        c.save()
        background_tasks.add_task(os.remove, pdf_file + ".pdf")
        background_tasks.add_task(shutil.rmtree, zip_folder)
        return f"{pdf_file}.pdf"
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in generate pdf : {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )

async def generate_pdf_pre(background_tasks: BackgroundTasks):
    try:
        parent_folder = os.path.join(zip_folder1, "temp_student_products")
        subfolders = [f.path for f in os.scandir(parent_folder) if f.is_dir()]
        pdf_files = []

        for folder_path in subfolders:
            folder_name = os.path.basename(folder_path)
            pdf_file = os.path.join(output_folder1, f"{folder_name}.pdf")
            image_files = [
                f for f in os.listdir(folder_path)
                if f.lower().endswith(("png", "jpg", "jpeg", "eps"))
            ]
            image_files.sort()

            if not image_files:
                continue

            c = canvas.Canvas(pdf_file, pagesize=letter)
            page_width, page_height = letter

            for image_file in image_files:
                image_path = os.path.join(folder_path, image_file)
                img = Image.open(image_path)
                img_width, img_height = img.size

                aspect_ratio = img_width / float(img_height)
                if aspect_ratio > 1:
                    new_width = min(page_width, img_width)
                    new_height = new_width / aspect_ratio
                else:
                    new_height = min(page_height, img_height)
                    new_width = new_height * aspect_ratio

                x_offset = (page_width - new_width) / 2
                y_offset = (page_height - new_height) / 2

                c.drawImage(
                    ImageReader(img), x_offset, y_offset, width=new_width, height=new_height
                )

                # Add filename label
                c.setFont("Helvetica", 10)
                c.drawString(x_offset, y_offset - 15, image_file)

                c.showPage()

            c.save()
            pdf_files.append(pdf_file)

        # Schedule cleanup tasks
        zip_path = await generate_zip_pre(background_tasks)
        for pdf_file in pdf_files:
            background_tasks.add_task(os.remove, pdf_file)
        background_tasks.add_task(shutil.rmtree, zip_folder)

        return zip_path;
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in generate pdf : {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal Server Error",
                "currentFrame": getframeinfo(currentframe()),
                "detail": str(traceback.format_exc()),
            },
        )