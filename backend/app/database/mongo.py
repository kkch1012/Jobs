from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings  # settings 객체 import
from app.models.mongo.job_post import JobPost

motor_client = AsyncIOMotorClient(settings.MONGO_URI) 

# MongoDB (Motor + Beanie) 초기화 함수
async def init_mongo():
    await init_beanie(
        database=motor_client[settings.MONGO_DB_NAME],  
        document_models=[JobPost]
    )
