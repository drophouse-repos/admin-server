from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from ai_models.TitanImageGenerator import TitanImageGenerator
from utils.error_check import handle_openai_error
from profanity_check import predict, predict_prob
from database.BASE import BaseDatabaseOperation
from inspect import currentframe, getframeinfo
from openai import AsyncOpenAI, OpenAI
from typing import Callable, List
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime
from db import get_db_ops
import traceback
import logging
import difflib
import asyncio
import base64
import openai
import json
import io
import os

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

key = os.environ.get("OPENAI_KEY")
client = AsyncOpenAI(api_key=key)

def get_ai_model() -> TitanImageGenerator:
	return TitanImageGenerator()

async def generate_prompts(prompts: List[str], numberOfPrompts: int):
	try:
		prompts_per_theme = numberOfPrompts // len(prompts)
		extra_prompts = numberOfPrompts % len(prompts)

		generated_prompts = []
		for i, prompt in enumerate(prompts):
			num_prompts_for_this_theme = prompts_per_theme + (1 if i < extra_prompts else 0)

			messages = [
				{
					"role": "system",
					"content": f"""
					You are a prompt engineering assistant with a focus on optimizing prompts for generating 
					high-quality images. You will be given a user prompt and the number of prompts to generate, 
					and you must return JSON with {num_prompts_for_this_theme} enhanced prompts. 
					The enhanced prompts should include every word of the original themes and have 15-25 words, 
					and split the themes with the number of prompts. Remember to only return valid JSON, 
					no more or less than {num_prompts_for_this_theme} prompts. Your suggestions should increase 
					the original themes' specificity, uniqueness, different from other prompts, and detail 
					to generate vivid and engaging images. The structure should be as follows:
					{{
						"Prompts": ["Prompt1", "Prompt2", ...., "Prompt{num_prompts_for_this_theme}"]
					}}
					"""
				},
				{
					"role": "user",
					"content": f"Theme: ['{prompt}'], NumberOfPrompts: {num_prompts_for_this_theme}"
				}
			]

			completion = await client.chat.completions.create(
				model="gpt-3.5-turbo",
				messages=messages,
				temperature=0.7,
				max_tokens=150
			)

			response = completion.choices[0].message.content
			response_json = json.loads(response)
			generated_prompts.extend(response_json['Prompts'])

		return generated_prompts
	except openai.OpenAIError as e:
		handle_openai_error(e)
		return {"Prompts": []}

async def generate_images(
	prompts: List[str]
):
	ai_model_primary = TitanImageGenerator()
	try:
		tasks = [ai_model_primary.generate_single_image(idx, prompt) for idx, prompt in enumerate(prompts)]
		return await asyncio.gather(*tasks, return_exceptions=True)
	except openai.OpenAIError as e:
		handle_openai_error(e)
	except HTTPException as http_exc:
		raise http_exc
	except Exception as e:
		logger.error(f"Error in assigning image task: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail={'message':f"Error in assigning image task: {str(e)}", 'currentFrame': getframeinfo(currentframe()), 'detail': str(traceback.format_exc())})