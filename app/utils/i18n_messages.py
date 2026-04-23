import json
import os

MESSAGES_PATH = os.path.join(os.path.dirname(__file__), "messages.json")

with open(MESSAGES_PATH, encoding="utf-8") as f:
    MESSAGES = json.load(f)

def translate(key: str, lang_code: str = "en") -> str:
    lang = lang_code if lang_code in MESSAGES else "en"
    return MESSAGES.get(lang, MESSAGES["en"]).get(key, key)
