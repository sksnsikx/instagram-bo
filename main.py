import os
import time
import random
import json
import logging
import base64
import io
import shutil
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# ===================== پیدا کردن مسیر کروم =====================
def get_chrome_path():
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"✅ کروم در مسیر {path} پیدا شد.")
            return path
    # اگر پیدا نشد، از `shutil.which` استفاده کن
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium-browser")
    if chrome:
        logger.info(f"✅ کروم در مسیر {chrome} پیدا شد.")
        return chrome
    logger.error("❌ کروم پیدا نشد!")
    return None

# ===================== توابع Selenium =====================
def get_driver():
    logger.info("🔄 راه‌اندازی مرورگر کروم...")
    options = Options()
    chrome_path = get_chrome_path()
    if chrome_path:
        options.binary_location = chrome_path
    else:
        raise Exception("کروم نصب نیست! لطفاً Dockerfile را بررسی کنید.")
    
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.page_load_strategy = 'eager'
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    logger.info("✅ مرورگر آماده شد.")
    return driver

def take_screenshot_base64(driver):
    try:
        return driver.get_screenshot_as_base64()
    except:
        return None

async def send_screenshot(update, driver, caption):
    b64 = take_screenshot_base64(driver)
    if b64:
        try:
            await update.message.reply_photo(
                photo=io.BytesIO(base64.b64decode(b64)),
                caption=caption,
                reply_markup=reset_keyboard
            )
        except Exception as e:
            logger.error(f"❌ خطا در ارسال اسکرین‌شات: {e}")

def find_element_with_multiple_selectors(driver, selectors, timeout=30):
    for by, selector in selectors:
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
        except:
            continue
    return None

async def start_registration(update, email, password, username_prefix="user"):
    logger.info(f"📧 شروع ثبت‌نام با ایمیل: {email}")
    driver = None
    username = None
    try:
        driver = get_driver()
        driver.get("https://www.instagram.com/accounts/emailsignup/")
        wait = WebDriverWait(driver, 120)

        logger.info("🔍 جستجوی فیلد ایمیل...")
        email_selectors = [
            (By.NAME, "emailOrPhone"),
            (By.CSS_SELECTOR, "input[name='emailOrPhone']"),
            (By.XPATH, "//input[@name='emailOrPhone']"),
            (By.XPATH, "//input[@type='email' or @name='emailOrPhone']"),
        ]
        email_input = find_element_with_multiple_selectors(driver, email_selectors, timeout=120)
        if not email_input:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                if inp.get_attribute("name") in ["emailOrPhone", "email"]:
                    email_input = inp
                    break
        if not email_input:
            await send_screenshot(update, driver, "❌ فیلد ایمیل پیدا نشد!")
            raise Exception("فیلد ایمیل پیدا نشد")

        email_input.clear()
        email_input.send_keys(email)

        password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        password_input.clear()
        password_input.send_keys(password)

        full_name_input = wait.until(EC.presence_of_element_located((By.NAME, "fullName")))
        full_name_input.clear()
        full_name = "User " + str(random.randint(1000, 9999))
        full_name_input.send_keys(full_name)

        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        username_input.clear()
        username = f"{username_prefix}_{random.randint(10000, 99999)}"
        username_input.send_keys(username)

        await send_screenshot(update, driver, "📝 مرحله ۱: فرم پر شد")

        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button']//span[text()='Submit']/..")))
        submit_button.click()
        time.sleep(3)

        await send_screenshot(update, driver, "⏳ مرحله ۲: در حال بررسی پاسخ")

        try:
            code_input = driver.find_element(By.NAME, "code")
            if code_input:
                await send_screenshot(update, driver, "✅ مرحله ۳: صفحه کد تأیید")
                return {"status": "waiting_for_code", "driver": driver, "username": username}
        except:
            pass

        page_text = driver.page_source.lower()
        if "try again" in page_text or "sorry" in page_text or "error" in page_text:
            await send_screenshot(update, driver, "❌ خطا از اینستاگرام")
            raise Exception("خطا از اینستاگرام")

        await send_screenshot(update, driver, "❓ صفحه ناشناخته")
        raise Exception("صفحه ناشناخته")

    except Exception as e:
        logger.error(f"❌ خطا: {e}")
        if driver:
            await send_screenshot(update, driver, f"❌ خطا: {str(e)[:200]}")
            driver.quit()
        return {"status": "error", "message": str(e)}

def submit_confirmation_code(driver, code):
    try:
        wait = WebDriverWait(driver, 120)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        code_input.clear()
        code_input.send_keys(code)
        time.sleep(1)
        driver.find_element(By.XPATH, "//div[@role='button']//span[text()='Submit']/..").click()
        time.sleep(5)
        cookies = driver.get_cookies()
        driver.quit()
        return {"status": "success", "cookies": cookies}
    except Exception as e:
        logger.error(f"❌ خطا در تأیید کد: {e}")
        driver.quit()
        return {"status": "error", "message": str(e)}

# ===================== هندلرهای ربات =====================
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text(
        "🤖 به ربات سازنده اکانت اینستاگرام خوش آمدید!\nلطفاً ایمیل خود را وارد کنید:",
        reply_markup=reset_keyboard
    )
    return EMAIL

async def receive_email(update: Update, context: CallbackContext):
    email = update.message.text
    user_id = update.effective_user.id
    user_data[user_id] = {"email": email}
    logger.info(f"📩 ایمیل دریافت شد: {email}")
    await update.message.reply_text("✅ ایمیل دریافت شد. حالا رمز عبور را وارد کنید:", reply_markup=reset_keyboard)
    return PASSWORD

async def receive_password(update: Update, context: CallbackContext):
    password = update.message.text
    user_id = update.effective_user.id
    user_data[user_id]["password"] = password
    logger.info(f"🔑 رمز عبور دریافت شد")
    await update.message.reply_text("⏳ در حال ایجاد اکانت...", reply_markup=reset_keyboard)
    result = await start_registration(update, user_data[user_id]["email"], password)
    if result["status"] == "waiting_for_code":
        user_data[user_id]["driver"] = result["driver"]
        user_data[user_id]["username"] = result["username"]
        await update.message.reply_text(
            f"📧 کد تأیید به ایمیل {user_data[user_id]['email']} ارسال شد.\nلطفاً کد ۶ رقمی را وارد کنید:",
            reply_markup=reset_keyboard
        )
        return CONFIRM_CODE
    else:
        await update.message.reply_text(f"❌ خطا: {result.get('message', 'نامشخص')}", reply_markup=reset_keyboard)
        user_data.pop(user_id, None)
        return ConversationHandler.END

async def receive_code(update: Update, context: CallbackContext):
    code = update.message.text
    user_id = update.effective_user.id
    driver = user_data[user_id].get("driver")
    if not driver:
        await update.message.reply_text("❌ نشست منقضی شده. دوباره با /start شروع کنید.", reply_markup=reset_keyboard)
        user_data.pop(user_id, None)
        return ConversationHandler.END
    result = submit_confirmation_code(driver, code)
    if result["status"] == "success":
        username = user_data[user_id]["username"]
        password = user_data[user_id]["password"]
        email = user_data[user_id]["email"]
        await update.message.reply_text(
            f"✅ اکانت ساخته شد!\n👤 {username}\n🔑 {password}\n📧 {email}",
            reply_markup=reset_keyboard
        )
        with open(f"account_{username}.json", "w") as f:
            json.dump({"username": username, "password": password, "email": email, "cookies": result["cookies"]}, f)
    else:
        await update.message.reply_text(f"❌ خطا: {result.get('message', 'نامشخص')}", reply_markup=reset_keyboard)
    user_data.pop(user_id, None)
    return ConversationHandler.END

async def reset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text("🔄 شروع دوباره... ایمیل را وارد کنید:", reply_markup=reset_keyboard)
    return EMAIL

async def cancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text("❌ لغو شد.", reply_markup=reset_keyboard)
    return ConversationHandler.END

def setup_bot():
    app_bot = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            CONFIRM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^🔄 شروع دوباره$"), reset)],
    )
    app_bot.add_handler(conv)
    return app_bot

@app.post("/webhook")
async def webhook(request: Request):
    global bot_app
    req = await request.json()
    if bot_app is None:
        return {"ok": False}
    await bot_app.process_update(Update.de_json(req, bot_app.bot))
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "ربات در حال اجرا است"}

@app.on_event("startup")
async def startup_event():
    global bot_app
    bot_app = setup_bot()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook: {WEBHOOK_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    global bot_app
    if bot_app:
        await bot_app.stop()
        await bot_app.shutdown()
