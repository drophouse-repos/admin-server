from inspect import currentframe, getframeinfo
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from fastapi import HTTPException
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import traceback
import requests
import logging
import shutil
import base64
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

VECTORIZER_MODE = os.environ.get("VECTORIZER_MODE")
VECTORIZER_SECRET = os.environ.get("VECTORIZER_SECRET")
VECTORIZER_TOKEN = os.environ.get("VECTORIZER_PRIVATE_TOKEN")

if VECTORIZER_MODE == 'prod':
    VECTORIZER_MODE = 'production'

zip_folder = "../student_module_zip_download"
output_folder = "../student_module_zip_download/zip"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)


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


async def clean_old_data():
    try:
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)

        zip_file = f"{zip_folder}/temp_student_products"
        if os.path.exists(zip_file):
            os.remove(zip_file + ".zip")

        shutil.rmtree(zip_folder)
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

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


def generate_vector_image(image_url, file_name):
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        response = requests.post(
            "https://vectorizer.ai/api/v1/vectorize",
            data={
                "mode": VECTORIZER_MODE,
                "image.url": image_url,
                "output.file_format": "eps",
            },
            auth=(VECTORIZER_TOKEN, VECTORIZER_SECRET),
        )
        size = file_name.split("_", 1)[0]
        if not os.path.exists(f"{output_folder}/{size}"):
            os.makedirs(f"{output_folder}/{size}")

        if response.status_code == requests.codes.ok:
            with open(f"{output_folder}/{size}/{file_name}.eps", "wb") as out:
                out.write(response.content)

            return f"{output_folder}/{size}/{file_name}.eps"
        else:
            logger.error("Error:", response.status_code, response.text)
            return False
    except HTTPException as http_exc:
        raise http_exc
    except Exception as error:
        logger.error(f"Error in generate_vector_image : {error}")
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
        result = shutil.make_archive(zip_file, "zip", output_folder)

        background_tasks.add_task(os.remove, zip_file + ".zip")
        background_tasks.add_task(shutil.rmtree, zip_folder)
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
