"""
language_bot.py
بوت تليجرام لاستقبال أوامر اختيار اللغة من المشتركين
يعمل كـ thread منفصل يستقبل updates من تليجرام
"""

import requests
import threading
import time
import logging
import json
import os

logger = logging.getLogger(__name__)

BOT_TOKEN = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SUBSCRIBERS_FILE = "/root/trade_lak_bot/data/subscribers.json"

LANG_MESSAGES = {
    "/start": (
        "مرحباً بك في Trade Lak Signal Bot! 🤖\n\n"
        "اختر لغتك / Choose your language:\n"
        "🇸🇦 /ar — العربية\n"
        "🇬🇧 /en — English"
    ),
    "/lang": (
        "اختر لغتك / Choose your language:\n"
        "🇸🇦 /ar — العربية\n"
        "🇬🇧 /en — English"
    ),
    "/ar": "✅ تم تعيين اللغة إلى العربية 🇸🇦\nستصلك الإشارات باللغة العربية.",
    "/en": "✅ Language set to English 🇬🇧\nYou will receive signals in English.",
}


def _load_subscribers():
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_subscribers(data):
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        logger.error(f"Error sending message: {e}")


class LanguageBot:
    """
    بوت صغير يستقبل أوامر /ar و /en من المشتركين
    ويحفظ تفضيلاتهم
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._last_update_id = 0

    def start(self):
        """بدء الاستماع للأوامر"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="LanguageBot")
        self._thread.start()
        logger.info("✅ LanguageBot started — listening for /ar and /en commands")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        """استطلاع تليجرام كل 5 ثوانٍ"""
        while self._running:
            try:
                self._process_updates()
            except Exception as e:
                logger.error(f"LanguageBot error: {e}")
            time.sleep(5)

    def _process_updates(self):
        """معالجة الرسائل الواردة"""
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": self._last_update_id + 1, "timeout": 5, "limit": 10},
                timeout=10
            )
            data = resp.json()
            if not data.get("ok"):
                return

            updates = data.get("result", [])
            for update in updates:
                self._last_update_id = update["update_id"]
                self._handle_update(update)

        except Exception as e:
            logger.debug(f"Poll error: {e}")

    def _handle_update(self, update):
        """معالجة update واحد"""
        message = update.get("message", {})
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        user_id = str(message.get("from", {}).get("id", ""))
        username = message.get("from", {}).get("username", "")

        if not text or not chat_id:
            return

        # معالجة الأوامر
        command = text.split()[0].lower()
        if command in LANG_MESSAGES:
            # حفظ تفضيل اللغة
            if command == "/ar":
                self._save_user_lang(user_id, username, "ar")
            elif command == "/en":
                self._save_user_lang(user_id, username, "en")

            # إرسال الرد
            _send_message(chat_id, LANG_MESSAGES[command])
            logger.info(f"User {username or user_id} set language via {command}")

    def _save_user_lang(self, user_id: str, username: str, lang: str):
        """حفظ لغة المستخدم"""
        subscribers = _load_subscribers()
        subscribers[user_id] = {
            "lang": lang,
            "username": username,
        }
        _save_subscribers(subscribers)


# ─── اختبار مباشر ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("LanguageBot module loaded OK ✅")
    print("To test: send /start, /ar, or /en to @Lamo_Dbot on Telegram")
