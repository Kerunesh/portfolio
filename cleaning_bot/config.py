import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Load pricing configuration
with open("config.json", "r", encoding="utf-8") as file:
    config_data = json.load(file)

CLEANING_TYPES = config_data.get("cleaning_types", {})
EXTRA_SERVICES = config_data.get("extra_services", {})