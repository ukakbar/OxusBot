import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_BOTFATHER_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]
CARD_NUMBER = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")

LOCATION_NAME = os.getenv("LOCATION_NAME", "Aydarkul, Oxus Adventure")
LOCATION_COORDS = os.getenv("LOCATION_COORDS", "40.800756,66.970392")

FEE_AMOUNT = int(os.getenv("FEE_AMOUNT", "350000"))
PRICE_COTTAGE_2 = int(os.getenv("PRICE_COTTAGE_2", "1500000"))
PRICE_COTTAGE_3 = int(os.getenv("PRICE_COTTAGE_3", "2000000"))
PRICE_YURT = int(os.getenv("PRICE_YURT", "800000"))
ORGANIZER_NICK = os.getenv("ORGANIZER_NICK", "@UkAkbar")
