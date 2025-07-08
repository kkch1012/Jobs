from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from app.models.job_postings import JobPosting  # 새 모델 임포트

motor_client = AsyncIOMotorClient(settings.MONGO_URI)

async def init_mongo():
    await init_beanie(
        database=motor_client[settings.MONGO_DB_NAME],
        document_models=[JobPosting],  # 여기에 새 모델 전달
    )
