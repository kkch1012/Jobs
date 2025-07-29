from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from app.models.mongo import MCPMessage, MultipleIntentSession

motor_client = AsyncIOMotorClient(settings.MONGO_URI)

async def init_mongo():
    await init_beanie(
        database=motor_client[settings.MONGO_DB_NAME],
        document_models=[MCPMessage, MultipleIntentSession],
    )

async def close_mongo():
    """MongoDB 연결을 안전하게 종료합니다."""
    if motor_client:
        motor_client.close()
