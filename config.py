import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Admin Telegram IDs (list)
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

# Payment card info
CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 1234 5678 9012")
CARD_HOLDER = os.getenv("CARD_HOLDER", "AZIZ KARIMOV")
BANK_NAME = os.getenv("BANK_NAME", "Uzcard")

# Payment settings
PAYMENT_AMOUNT = int(os.getenv("PAYMENT_AMOUNT", "50000"))  # UZS
PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", "300"))  # 5 minutes in seconds

# Supabase PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "")
