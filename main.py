import os
import time
import random
import json
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ===================== تنظیمات =====================
TELEGRAM_TOKEN = "8591528173:AAFNV8iJqUPuWDsCj7QATClk-qUU9GH-IKg"  # توکن شما
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://your-app.railway.app")
WEBHOOK_URL = f"{RAILWAY_PUBLIC_DOMAIN}/webhook"

app = FastAPI()

# وضعیت‌های مکالمه
EMAIL, PASSWORD, CONFIRM_CODE = range(3)

# حافظه موقت کاربران (دیکشنری)
user_data = {}

# ===================== توابع Selenium =====================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def start_registration(email, password, username_prefix="user"):
    """مرحله اول ثبت‌نام: پر کردن فرم ایمیل و رمز، بازگرداندن درایور برای مرحله کد"""
    driver = None
    try:
        driver = get_driver()
        driver.get("https://www.instagram.com/accounts/emailsignup/")
        time.sleep(3)

        # کلیک روی گزینه ثبت‌نام با ایمیل (اگر موجود باشد)
        try:
            email_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Sign up with email')]")
            email_link.click()
            time.sleep(2)
        except:
            pass  # قبلاً صفحه ایمیل است

        # پر کردن فرم
        driver.find_element(By.NAME, "emailOrPhone").send_keys(email)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "fullName").send_keys("User " + str(random.randint(1000, 9999)))
        username = f"{username_prefix}_{random.randint(10000, 99999)}"
        driver.find_element(By.NAME, "username").send_keys(username)

        # کلیک دکمه بعد
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        # اکنون در صفحه درخواست کد تأیید هستیم
        return {"status": "waiting_for_code", "driver": driver, "username": username}
    except Exception as e:
        if driver:
            driver.quit()
        return {"status": "error", "message": str(e)}

def submit_confirmation_code(driver, code):
    """مرحله دوم: وارد کردن کد تأیید و نهایی‌سازی"""
    try:
        wait = WebDriverWait(driver, 30)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        code_input.send_keys(code)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(5)
        cookies = driver.get_cookies()
        driver.quit()
        return {"status": "success", "cookies": cookies}
    except Exception as e:
        driver.quit()
        return {"status": "error", "message": str(e)}

# ===================== هندلرهای ربات =====================
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🤖 به ربات سازنده اکانت اینستاگرام خوش آمدید!\n"
        "لطفاً ایمیل خود را وارد کنید:"
    )
    return EMAIL

async def receive_email(update: Update, context: CallbackContext):
    email = update.message.text
    user_id = update.effective_user.id
    user_data[user_id] = {"email": email}
    await update.message.reply_text("✅ ایمیل دریافت شد. حالا رمز عبور مورد نظر را وارد کنید:")
    return PASSWORD

async def receive_password(update: Update, context: CallbackContext):
    password = update.message.text
    user_id = update.effective_user.id
    user_data[user_id]["password"] = password
    await update.message.reply_text("⏳ در حال ایجاد اکانت... لطفاً صبر کنید.")

    # شروع ثبت‌نام
    result = start_registration(user_data[user_id]["email"], password)
    if result["status"] == "waiting_for_code":
        user_data[user_id]["driver"] = result["driver"]
        user_data[user_id]["username"] = result["username"]
        await update.message.reply_text(
            f"📧 کد تأیید به ایمیل {user_data[user_id]['email']} ارسال شد.\n"
            "لطفاً کد ۶ رقمی را وارد کنید:"
        )
        return CONFIRM_CODE
    else:
        await update.message.reply_text(f"❌ خطا: {result.get('message', 'نامشخص')}")
        user_data.pop(user_id, None)
        return ConversationHandler.END

async def receive_code(update: Update, context: CallbackContext):
    code = update.message.text
    user_id = update.effective_user.id
    driver = user_data[user_id].get("driver")
    if not driver:
        await update.message.reply_text("❌ نشست منقضی شده. دوباره با /start شروع کنید.")
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
            f"(کوکی‌ها نیز در سرور ذخیره شدند)"
        )
        # ذخیره کوکی‌ها در فایل (اختیاری)
        with open(f"account_{username}.json", "w") as f:
            json.dump({"username": username, "password": password, "email": email, "cookies": result["cookies"]}, f)
    else:
        await update.message.reply_text(f"❌ خطا در تأیید کد: {result.get('message', 'نامشخص')}")

    user_data.pop(user_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data and "driver" in user_data[user_id]:
        user_data[user_id]["driver"].quit()
    user_data.pop(user_id, None)
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

# ===================== راه‌اندازی ربات =====================
def setup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            CONFIRM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    return application

# ===================== FastAPI =====================
@app.post("/webhook")
async def webhook(request: Request):
    req = await request.json()
    bot_app = setup_bot()
    await bot_app.process_update(Update.de_json(req, bot_app.bot))
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "ربات اینستاگرام ساز در حال اجرا است"}

@app.on_event("startup")
async def set_webhook():
    bot_app = setup_bot()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to {WEBHOOK_URL}")
