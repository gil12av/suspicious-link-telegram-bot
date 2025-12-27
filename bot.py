# =============================================================================
# בוט טלגרם לבדיקת קישורים חשודים
# קובץ זה מכיל את הלוגיקה הראשית של הבוט:
# - טיפול בפקודת /start
# - עיבוד הודעות טקסט המכילות קישורים
# - שילוב בין ניתוח טכני של הקישור לבין סיווג ML
# - הצגת תוצאות בדיקה מפורטות למשתמש
# =============================================================================

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram import Update
from linkChecker import analyze_link

import logging
from ml.ml_infer import ml_predict
from utils import extract_urls

# הגדרת לוג
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# תגובה לפעולת /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("hello there! please send me the link and i will check is it safe 🔍")

def fmt(value, suffix=""):
    return "Unknown" if value is None else f"{value}{suffix}"

# -- תגובה לכל הודעה --
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
   text = update.message.text.strip()
   chat_id = update.effective_chat.id

   logger.info(f"📥 Message received: {text}")
   
   urls = extract_urls(text)
   logger.info(f"🔗 URLs extracted: {urls}")

   if not urls:
        await update.message.reply_text("please send a valid link 💡")
        logger.warning("⚠️ No URL found in message.")
        return

   url = urls[0]
   for url in urls:
        await update.message.reply_text(f"📡 Got link: {url} – checking...")
        try:
            result = analyze_link(url)
            feeds = result.get("feeds_hit") or []
            feeds_line = "🧰 Feeds: Not listed" if not feeds else f"🛑 Feeds: {', '.join(feeds)}"
            ssl_str = "Valid ✅" if result["ssl_valid"] is True else ("Invalid ❌" if result["ssl_valid"] is False else "Unknown")
            age_str = "Unknown" if result["domain_age_days"] is None else f'{result["domain_age_days"]} Days'
            redirects_str = "Unknown" if result["num_redirects"] is None else str(result["num_redirects"])

            ml_out = ml_predict(message_text=text, url=text, agent_result=result)
            label = ml_out["label"]
            conf  = ml_out["confidence"]
            ml_line = f"🧪 ML: {label}" + (f" ({conf:.2f})" if conf is not None else "")

            msg = (
                f"🔗 Link: {url}\n"
                f"🌐 Domain: {result['domain']}\n"
                f"📅 Domain age: {age_str}\n"
                f"🔒 SSL: {ssl_str}\n"
                f"↪️  Number of Redirect: {redirects_str}\n\n"
                f"{feeds_line}\n\n"
                f"{ml_line}\n\n"
                f"🧠 {result['recommendation']}"
            )
            await update.message.reply_text(msg)
        except Exception as e:
            logging.exception("link analyze failed")
            await update.message.reply_text(f"❌ Error checking {url}, try again later")


# מטפל שגיאות גלובלי – כדי שלא תראה שוב את 'No error handlers are registered'
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.exception("Unhandled error", exc_info=context.error)
    if hasattr(update, "message") and update.message:
        await update.message.reply_text("❌ An unexpected error occurred, we are handling it. ")



# -- נקודת ההפעלה של הבוט --
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")  # גישה לקובץ env

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)

    print("🤖 bot running…")
    app.run_polling()