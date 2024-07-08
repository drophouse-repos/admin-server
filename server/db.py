from typing import Callable  # , Type
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from database.BASE import BaseDatabaseOperation
import os

load_dotenv(verbose=True, override=True)


mongodb_client = None
db = None
MONGO_URL = os.environ.get("MONGO_URL")
DB_ENV = os.environ.get("DB_ENV")

async def connect_to_mongo():
    global mongodb_client, db
    mongodb_client = AsyncIOMotorClient(MONGO_URL)
    
    if DB_ENV and DB_ENV == "prod":
        db = mongodb_client.UserInfo
    else:
        db = mongodb_client.DEV
    print("connected to mongo")


async def close_mongo_connection():
    mongodb_client.close()


def get_database():
    return db


def get_db_ops(class_type: type[BaseDatabaseOperation]) -> Callable:
    def dependency():
        db = get_database()
        return class_type(db)

    return dependency
