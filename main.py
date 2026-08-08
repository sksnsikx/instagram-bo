import os
import time
import random
import json
import logging
import base64
import io
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackContext
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ===================== راه‌اندازی لاگ =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== تنظیمات =====================
TELEGRAM_TOKEN = "8591528173:AAFNV8iJqUPuWDsCj7QATClk-qUU9GH-IKg"
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://instagram-bo-production.up.railway.app")
WEBHOOK_URL = f"{RAILWAY_PUBLIC_DOMAIN}/webhook"

app = FastAPI()

EMAIL, PASSWORD, CONFIRM_CODE = range(3)
user_data = {}
bot_app = None

reset_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("🔄 شروع دوباره")]],
    resize_keyboard=True
)

# ===================== توابع Selenium =====================
def get_driver():
    logger.info("🔄 راه‌اندازی مرورگر کروم...")
    options = Options()
    options.binary_location = "/usr/bin/google-chrome"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.page_load_strategy = 'eager'  # لود سریع‌تر صفحه
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    logger.info("✅ مرورگر آماده شد.")
    return driver

def take_screenshot_base64(driver):
    try:
        return driver.get_screenshot_as_base64()
    except Exception as e:
        logger.error(f"❌ خطا در گرفتن اسکرین‌شات: {str(e)}")
        return None

async def send_screenshot(update, driver, caption):
    screenshot_base64 = take_screenshot_base64(driver)
    if screenshot_base64:
        try:
            photo_bytes = base64.b64decode(screenshot_base64)
            await update.message.reply_photo(
                photo=io.BytesIO(photo_bytes),
                caption=caption,
                reply_markup=reset_keyboard
            )
            logger.info(f"📸 اسکرین‌شات ارسال شد: {caption}")
        except Exception as e:
            logger.error(f"❌ خطا در ارسال اسکرین‌شات: {str(e)}")
    else:
        await update.message.reply_text(f"⚠️ اسکرین‌شات گرفته نشد: {caption}")

async def start_registration(update, email, password, username_prefix="user"):
    logger.info(f"📧 شروع ثبت‌نام با ایمیل: {email}")
    driver = None
    username = None
    try:
        driver = get_driver()
        logger.info("🌐 باز کردن صفحه ثبت‌نام اینستاگرام...")
        driver.get("https://www.instagram.com/accounts/emailsignup/")
        
        wait = WebDriverWait(driver, 45)
        
        # ===== پیدا کردن فیلد ایمیل =====
        logger.info("🔍 جستجوی فیلد ایمیل...")
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "emailOrPhone")))
        email_input.clear()
        email_input.send_keys(email)
        logger.info("✅ فیلد ایمیل پر شد.")
        
        # ===== پیدا کردن فیلد رمز عبور =====
        logger.info("🔍 جستجوی فیلد رمز عبور...")
        password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        password_input.clear()
        password_input.send_keys(password)
        logger.info("✅ فیلد رمز عبور پر شد.")
        
        # ===== پیدا کردن فیلد نام کامل =====
        logger.info("🔍 جستجوی فیلد نام کامل...")
        full_name_input = wait.until(EC.presence_of_element_located((By.NAME, "fullName")))
        full_name_input.clear()
        full_name = "User " + str(random.randint(1000, 9999))
        full_name_input.send_keys(full_name)
        logger.info(f"✅ فیلد نام کامل پر شد: {full_name}")
        
        # ===== پیدا کردن فیلد نام کاربری =====
        logger.info("🔍 جستجوی فیلد نام کاربری...")
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        username_input.clear()
        username = f"{username_prefix}_{random.randint(10000, 99999)}"
        username_input.send_keys(username)
        logger.info(f"✅ فیلد نام کاربری پر شد: {username}")
        
        # ارسال اسکرین‌شات مرحله ۱
        await send_screenshot(update, driver, "📝 مرحله ۱: فرم پر شد، در حال ارسال به اینستاگرام...")
        
        # ===== پیدا کردن دکمه Submit =====
        logger.info("🖱️ جستجوی دکمه ارسال...")
        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button']//span[text()='Submit']/..")))
        submit_button.click()
        logger.info("✅ دکمه ارسال کلیک شد.")
        
        time.sleep(3)
        
        # ارسال اسکرین‌شات مرحله ۲
        await send_screenshot(update, driver, "⏳ مرحله ۲: در حال بررسی پاسخ اینستاگرام...")
        
        # ===== بررسی نتیجه =====
        try:
            code_input = driver.find_element(By.NAME, "code")
            if code_input:
                logger.info("✅ صفحه کد تأیید پیدا شد! ایمیل با موفقیت ارسال شده است.")
                await send_screenshot(update, driver, "✅ مرحله ۳: صفحه کد تأیید! ایمیل ارسال شد.")
                return {"status": "waiting_for_code", "driver": driver, "username": username}
        except:
            pass
        
        page_text = driver.page_source.lower()
        if "try again" in page_text or "sorry" in page_text or "error" in page_text or "problem" in page_text:
            await send_screenshot(update, driver, "❌ مرحله ۴: خطا از اینستاگرام (آی‌پی مسدود یا کپچا)")
            raise Exception("اینستاگرام خطا داده است (احتمالاً آی‌پی مسدود یا کپچا نیاز است).")
        
        await send_screenshot(update, driver, "❓ مرحله ۵: صفحه ناشناخته! ثبت‌نام موفق نبود.")
        raise Exception("صفحه ناشناخته! ثبت‌نام موفق نبوده است.")
        
    except Exception as e:
        logger.error(f"❌ خطا در start_registration: {str(e)}")
        if driver:
            await send_screenshot(update, driver, f"❌ خطا: {str(e)[:200]}")
            driver.quit()
        return {"status": "error", "message": str(e)}

def submit_confirmation_code(driver, code):
    logger.info(f"🔢 ارسال کد تأیید: {code}")
    try:
        wait = WebDriverWait(driver, 45)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        code_input.clear()
        code_input.send_keys(code)
        time.sleep(1)
        submit_button = driver.find_element(By.XPATH, "//div[@role='button']//span[text()='Submit']/..")
        submit_button.click()
        time.sleep(5)
        cookies = driver.get_cookies()
        driver.quit()
        logger.info("✅ کد تأیید شد و اکانت ساخته شد.")
        return {"status": "success", "cookies": cookies}
    except Exception as e:
        logger.error(f"❌ خطا در submit_confirmation_code: {str(e)}")
        driver.quit()
        return {"status": "error", "message": str(e)}

# ===================== هندلرهای ربات =====================
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text(
        "🤖 به ربات سازنده اکانت اینستاگرام خوش آمدید!\n"
        "لطفاً ایمیل خود را وارد کنید:",
        reply_markup=reset_keyboard
    )
    return EMAIL

async def receive_email(update: Update, context: CallbackContext):
    email = update.message.text
    user_id = update.effective_user.id
    user_data[user_id] = {"email": email}
    logger.info(f"📩 ایمیل دریافت شد از کاربر {user_id}: {email}")
    await update.message.reply_text(
        "✅ ایمیل دریافت شد. حالا رمز عبور مورد نظر را وارد کنید:",
        reply_markup=reset_keyboard
    )
    return PASSWORD

async def receive_password(update: Update, context: CallbackContext):
    password = update.message.text
    user_id = update.effective_user.id
    user_data[user_id]["password"] = password
    logger.info(f"🔑 رمز عبور دریافت شد از کاربر {user_id}")
    await update.message.reply_text(
        "⏳ در حال ایجاد اکانت... لطفاً صبر کنید.",
        reply_markup=reset_keyboard
    )
    result = await start_registration(update, user_data[user_id]["email"], password)
    if result["status"] == "waiting_for_code":
        user_data[user_id]["driver"] = result["driver"]
        user_data[user_id]["username"] = result["username"]
        logger.info(f"⏳ منتظر کد تأیید برای کاربر {user_id}, ایمیل: {user_data[user_id]['email']}")
        await update.message.reply_text(
            f"📧 کد تأیید به ایمیل {user_data[user_id]['email']} ارسال شد.\n"
            "لطفاً کد ۶ رقمی را وارد کنید:",
            reply_markup=reset_keyboard
        )
        return CONFIRM_CODE
    else:
        logger.error(f"❌ خطا در ثبت‌نام کاربر {user_id}: {result.get('message', 'نامشخص')}")
        await update.message.reply_text(
            f"❌ خطا: {result.get('message', 'نامشخص')}",
            reply_markup=reset_keyboard
        )
        user_data.pop(user_id, None)
        return ConversationHandler.END

async def receive_code(update: Update, context: CallbackContext):
    code = update.message.text
    user_id = update.effective_user.id
    logger.info(f"📥 کد تأیید دریافت شد از کاربر {user_id}: {code}")
    driver = user_data[user_id].get("driver")
    if not driver:
        await update.message.reply_text(
            "❌ نشست منقضی شده. دوباره با /start شروع کنید.",
            reply_markup=reset_keyboard
        )
        user_data.pop(user_id, None)
        return ConversationHandler.END
    result = submit_confirmation_code(driver, code)
    if result["status"] == "success":
        username = user_data[user_id]["username"]
        password = user_data[user_id]["password"]
        email = user_data[user_id]["email"]
        await update.message.reply_text(
            f"✅ اکانت با موفقیت ساخته شد!\n"
            f"👤 نام کاربری: `{username}`\n"
            f"🔑 رمز عبور: `{password}`\n"
            f"📧 ایمیل: `{email}`\n"
            f"(کوکی‌ها نیز در سرور ذخیره شدند)",
            reply_markup=reset_keyboard
        )
        with open(f"account_{username}.json", "w") as f:
            json.dump({"username": username, "password": password, "email": email, "cookies": result["cookies"]}, f)
    else:
        await update.message.reply_text(
            f"❌ خطا در تأیید کد: {result.get('message', 'نامشخص')}",
            reply_markup=reset_keyboard
        )
    user_data.pop(user_id, None)
    return ConversationHandler.END

async def reset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text(
        "🔄 شروع دوباره... لطفاً ایمیل خود را وارد کنید:",
        reply_markup=reset_keyboard
    )
    return EMAIL

async def cancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=reset_keyboard
    )
    return ConversationHandler.END

def setup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            CONFIRM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("reset", reset),
            MessageHandler(filters.Regex("^🔄 شروع دوباره$"), reset),
        ],
    )
    application.add_handler(conv_handler)
    return application

# ===================== FastAPI =====================
@app.post("/webhook")
async def webhook(request: Request):
    global bot_app
    req = await request.json()
    if bot_app is None:
        return {"ok": False, "error": "Bot not initialized"}
    await bot_app.process_update(Update.de_json(req, bot_app.bot))
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "ربات اینستاگرام ساز در حال اجرا است"}

@app.on_event("startup")
async def startup_event():
    global bot_app
    logger.info("🚀 راه‌اندازی ربات تلگرام...")
    bot_app = setup_bot()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook تنظیم شد: {WEBHOOK_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    global bot_app
    if bot_app:
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("🛑 ربات متوقف شد.")
