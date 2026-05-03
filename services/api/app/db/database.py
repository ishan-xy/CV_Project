from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from services.api.app.core.config import get_settings

settings = get_settings()

client: AsyncIOMotorClient = None
database: AsyncIOMotorDatabase = None


async def connect_db():
    global client, database
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.DATABASE_NAME]
    await init_room_config()


async def disconnect_db():
    global client
    if client:
        client.close()


async def get_database() -> AsyncIOMotorDatabase:
    return database


async def init_room_config():
    config_collection = database["room_config"]
    existing = await config_collection.find_one({"_id": "hotel_config"})
    if not existing:
        await config_collection.insert_one({
            "_id": "hotel_config",
            "total_floors": 8,
            "rooms_per_floor": 50,
            "room_type_distribution": {
                "Standard": 20,
                "Deluxe": 14,
                "Super Deluxe": 9,
                "Executive": 5,
                "Suite": 2
            }
        })