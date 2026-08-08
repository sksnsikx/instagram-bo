import os
import time
import random
import json
import logging
import base64
import re
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    logger.info("✅ مرورگر آماده شد.")
    return driver

def log_all_inputs(driver):
    """لاگ کردن تمام input های صفحه برای دیباگ"""
    inputs = driver.find_elements(By.TAG_NAME, "input")
    logger.info(f"📋 تعداد input های صفحه: {len(inputs)}")
    for inp in inputs:
        try:
            name = inp.get_attribute("name")
            type_ = inp.get_attribute("type")
            placeholder = inp.get_attribute("placeholder")
            logger.info(f"   - name: {name}, type: {type_}, placeholder: {placeholder}")
        except:
            pass

def take_screenshot(driver, name="screenshot.png"):
    try:
        screenshot = driver.get_screenshot_as_base64()
        logger.info(f"📸 اسکرین‌شات ذخیره شد: {name}")
        # می‌توانید برای ذخیره در فایل:
        # with open(name, "wb") as f:
        #     f.write(base64.b64decode(screenshot))
    except Exception as e:
        logger.error(f"❌ خطا در گرفتن اسکرین‌شات: {str(e)}")

def start_registration(email, password, username_prefix="user"):
    logger.info(f"📧 شروع ثبت‌نام با ایمیل: {email}")
    driver = None
    try:
        driver = get_driver()
        logger.info("🌐 باز کردن صفحه ثبت‌نام اینستاگرام...")
        driver.get("https://www.instagram.com/accounts/emailsignup/")
        wait = WebDriverWait(driver, 20)
        
        # صبر برای لود شدن صفحه
        time.sleep(5)
        
        # لاگ کردن تمام input ها برای دیباگ
        log_all_inputs(driver)
        
        # تلاش برای پیدا کردن فیلد ایمیل با روش‌های مختلف
        logger.info("🔍 جستجوی فیلد ایمیل...")
        email_input = None
        
        # روش ۱: با استفاده از JavaScript (مقاوم‌ترین روش)
        try:
            email_input = driver.execute_script("""
                return document.querySelector('input[name="emailOrPhone"]') || 
                       document.querySelector('input[type="email"]') ||
                       document.querySelector('input[placeholder*="email" i]') ||
                       document.querySelector('input[placeholder*="phone" i]') ||
                       document.querySelector('input[autocomplete="email"]') ||
                       document.querySelector('input[autocomplete="username"]') ||
                       document.querySelector('input[type="text"]:not([name*="user"]):not([name*="full"])')
            """)
            if email_input:
                logger.info("✅ فیلد ایمیل با JavaScript پیدا شد.")
        except:
            pass
        
        # روش ۲: اگر JavaScript کار نکرد، از WebDriverWait استفاده کن
        if not email_input:
            selectors = [
                (By.NAME, "emailOrPhone"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='emailOrPhone']"),
                (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
                (By.CSS_SELECTOR, "input[autocomplete='email']"),
                (By.XPATH, "//input[@name='emailOrPhone']"),
                (By.XPATH, "//input[@type='email']"),
            ]
            for by, selector in selectors:
                try:
                    email_input = wait.until(EC.presence_of_element_located((by, selector)))
                    if email_input:
                        logger.info(f"✅ فیلد ایمیل با selector {selector} پیدا شد.")
                        break
                except:
                    continue
        
        if not email_input:
            take_screenshot(driver, "error_screenshot.png")
            log_all_inputs(driver)
            raise Exception("فیلد ایمیل پیدا نشد. صفحه ممکن است تغییر کرده باشد.")
        
        # پر کردن فرم با JavaScript (مقاوم‌تر از send_keys)
        logger.info("✏️ پر کردن فرم با JavaScript...")
        driver.execute_script("arguments[0].value = arguments[1];", email_input, email)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
        
        # پیدا کردن و پر کردن سایر فیلدها
        password_input = driver.execute_script("""
            return document.querySelector('input[type="password"]') || 
                   document.querySelector('input[name="password"]')
        """)
        if password_input:
            driver.execute_script("arguments[0].value = arguments[1];", password_input, password)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_input)
        else:
            raise Exception("فیلد رمز عبور پیدا نشد.")
        
        # نام کامل
        full_name_input = driver.execute_script("""
            return document.querySelector('input[name="fullName"]') || 
                   document.querySelector('input[placeholder*="full" i]') ||
                   document.querySelector('input[placeholder*="name" i]')
        """)
        if full_name_input:
            full_name = "User " + str(random.randint(1000, 9999))
            driver.execute_script("arguments[0].value = arguments[1];", full_name_input, full_name)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", full_name_input)
        else:
            logger.warning("⚠️ فیلد نام کامل پیدا نشد، ادامه می‌دهیم...")
        
        # نام کاربری
        username_input = driver.execute_script("""
            return document.querySelector('input[name="username"]') || 
                   document.querySelector('input[placeholder*="user" i]')
        """)
        if username_input:
            username = f"{username_prefix}_{random.randint(10000, 99999)}"
            driver.execute_script("arguments[0].value = arguments[1];", username_input, username)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", username_input)
        else:
            logger.warning("⚠️ فیلد نام کاربری پیدا نشد، ادامه می‌دهیم...")
        
        # کلیک روی دکمه submit
        logger.info("🖱️ کلیک روی دکمه ارسال فرم...")
        submit_button = driver.execute_script("""
            return document.querySelector('button[type="submit"]') || 
                   document.querySelector('button[type="button"]') ||
                   document.querySelector('button[class*="submit"]')
        """)
        if submit_button:
            driver.execute_script("arguments[0].click();", submit_button)
        else:
            # اگر دکمه پیدا نشد، از کلاس‌های رایج استفاده کن
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                try:
                    if "next" in btn.text.lower() or "continue" in btn.text.lower() or "sign up" in btn.text.lower():
                        btn.click()
                        break
                except:
                    pass
        
        time.sleep(5)
        logger.info("✅ فرم ارسال شد. منتظر دریافت کد از ایمیل هستیم...")
        
        return {"status": "waiting_for_code", "driver": driver, "username": username}
    except Exception as e:
        logger.error(f"❌ خطا در start_registration: {str(e)}")
        if driver:
            take_screenshot(driver, "error_screenshot.png")
            driver.quit()
        return {"status": "error", "message": str(e)}

def submit_confirmation_code(driver, code):
    logger.info(f"🔢 ارسال کد تأیید: {code}")
    try:
        wait = WebDriverWait(driver, 30)
        code_input = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        driver.execute_script("arguments[0].value = arguments[1];", code_input, code)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", code_input)
        time.sleep(1)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
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
    await update.message.reply_text(
        "🤖 به ربات سازنده اکانت اینستاگرام خوش آمدید!\n"
        "لطفاً ایمیل خود را وارد کنید:"
    )
    return EMAIL

async def receive_email(update: Update, context: CallbackContext):
    email = update.message.text
    user_id = update.effective_user.id
    user_data[user_id] = {"email": email}
    logger.info(f"📩 ایمیل دریافت شد از کاربر {user_id}: {email}")
    await update.message.reply_text("✅ ایمیل دریافت شد. حالا رمز عبور مورد نظر را وارد کنید:")
    return PASSWORD

async def receive_password(update: Update, context: CallbackContext):
    password = update.message.text
    user_id = update.effective_user.id
    user_data[user_id]["password"] = password
    logger.info(f"🔑 رمز عبور دریافت شد از کاربر {user_id}")
    await update.message.reply_text("⏳ در حال ایجاد اکانت... لطفاً صبر کنید.")
    result = start_registration(user_data[user_id]["email"], password)
    if result["status"] == "waiting_for_code":
        user_data[user_id]["driver"] = result["driver"]
        user_data[user_id]["username"] = result["username"]
        logger.info(f"⏳ منتظر کد تأیید برای کاربر {user_id}, ایمیل: {user_data[user_id]['email']}")
        await update.message.reply_text(
            f"📧 کد تأیید به ایمیل {user_data[user_id]['email']} ارسال شد.\n"
            "لطفاً کد ۶ رقمی را وارد کنید:"
        )
        return CONFIRM_CODE
    else:
        logger.error(f"❌ خطا در ثبت‌نام کاربر {user_id}: {result.get('message', 'نامشخص')}")
        await update.message.reply_text(f"❌ خطا: {result.get('message', 'نامشخص')}")
        user_data.pop(user_id, None)
        return ConversationHandler.END

async def receive_code(update: Update, context: CallbackContext):
    code = update.message.text
    user_id = update.effective_user.id
    logger.info(f"📥 کد تأیید دریافت شد از کاربر {user_id}: {code}")
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
