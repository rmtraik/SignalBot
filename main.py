# main_bot.py
import pandas as pd
from datetime import datetime
import time
from telegram import Bot
import sys 
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters # تأكد من هذا الاستيراد
import asyncio

# --- استيراد الإعدادات والمكونات ---
try:
    from config.telegram_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    print("Main: Successfully loaded Telegram config.")
except ImportError:
    print("Main Warning: config/telegram_config.py not found. Using placeholders for Telegram.")
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER"
    TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER"

try:
    from config.api_keys_config import QUOTEX_EMAIL, QUOTEX_PASSWORD # استيراد بيانات اعتماد Quotex
    print("Main: Successfully loaded Quotex credentials from api_keys_config.")
except ImportError:
    print("Main Warning: Quotex credentials not found in config/api_keys_config.py. Using placeholders.")
    QUOTEX_EMAIL = "your_quotex_email_placeholder@example.com"
    QUOTEX_PASSWORD = "your_quotex_password_placeholder"

try:
    from data_fetcher import fetch_data_from_source 
    print("Main: Successfully loaded data_fetcher.")
except ImportError:
    print("Main CRITICAL ERROR: data_fetcher.py not found. Bot cannot run.")
    sys.exit(1)

try:
    from signal_engine import get_single_signal_from_engine
    print("Main: Successfully loaded signal_engine.")
except ImportError:
    print("Main CRITICAL ERROR: signal_engine.py not found. Bot cannot run.")
    sys.exit(1)

try:
    from broker.quotex_executor import setup_browser, login_quotex, place_trade, close_browser
    print("Main: Successfully loaded Quotex executor.")
except ImportError:
    print("Main Warning: broker/quotex_executor.py not found. Trading functions will be simulated.")
    def setup_browser(headless=True, browser_type="chrome"): print("Mock: setup_browser"); return "mock_driver"
    def login_quotex(driver, email, password): print("Mock: login_quotex"); return True
    def place_trade(driver, asset, direction, amount, duration): print(f"Mock: place_trade for {asset}"); return True
    def close_browser(driver): print("Mock: close_browser")


# ========== إعدادات المستخدم الرئيسية للتشغيل ==========
# !!! تأكد أن هذا السطر موجود هنا في النطاق العام !!!
ACTIVE_DATA_SOURCE = "TWELVEDATA" # اختر: "IQOPTION" أو "TWELVEDATA"

# إعدادات Quotex (الآن يتم تحميلها من api_keys_config.py، لذا لا حاجة لتعريفها هنا)
# Q_EMAIL = QUOTEX_EMAIL 
# Q_PASSWORD = QUOTEX_PASSWORD

TRADE_AMOUNT = 1
TRADE_DURATION = "1m" 
ANALYSIS_FRAMES = ["15min", "30min", "1h"] 
CANDLE_COUNT_TO_FETCH = 250 

ASSETS_TO_MONITOR = [
    {"COMMON_NAME": "EUR/USD", "IQOPTION_SYMBOL": "EURUSD", "TWELVEDATA_SYMBOL": "EUR/USD", "QUOTEX_SYMBOL": "EURUSD"},
    {"COMMON_NAME": "GBP/USD", "IQOPTION_SYMBOL": "GBPUSD", "TWELVEDATA_SYMBOL": "GBP/USD", "QUOTEX_SYMBOL": "GBPUSD"},
    {"COMMON_NAME": "USD/JPY", "IQOPTION_SYMBOL": "USDJPY", "TWELVEDATA_SYMBOL": "USD/JPY", "QUOTEX_SYMBOL": "USDJPY"},
]

# ... (بقية الكود: تهيئة بوت تيليجرام، دوال مساعدة، معالجات الأوامر، background_analysis_loop, post_init, main) ...

# --- معالجات أوامر تيليجرام ---
async def start_command(update, context: ContextTypes.DEFAULT_TYPE) -> None: # Update غير مستخدمة هنا
    user = update.effective_user
    await update.message.reply_html(
        rf"أهلاً {user.mention_html()}! أنا بوت تحليل الإشارات. حاليًا أراقب تلقائيًا.",
    )

async def status_command(update, context: ContextTypes.DEFAULT_TYPE) -> None: # Update غير مستخدمة هنا
    status_message = f"""
    📊 **حالة البوت** 📊
    مصدر البيانات النشط: {ACTIVE_DATA_SOURCE}
    الأصول المراقبة: {[a['COMMON_NAME'] for a in ASSETS_TO_MONITOR]}
    الأطر الزمنية للتحليل: {ANALYSIS_FRAMES}
    """
    await update.message.reply_text(status_message, parse_mode="Markdown")

async def check_asset_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not context.args:
            await update.message.reply_text("الاستخدام: /check <ASSET_SYMBOL> (مثال: /check EUR/USD)")
            return

        asset_to_check_common = context.args[0].upper()
        await update.message.reply_text(f"🔍 جاري تحليل {asset_to_check_common} على الأطر الزمنية {ANALYSIS_FRAMES}...")

        asset_config_found = next((a for a in ASSETS_TO_MONITOR if a["COMMON_NAME"] == asset_to_check_common), None)
        if not asset_config_found:
            await update.message.reply_text(f"لم يتم العثور على الأصل {asset_to_check_common} في قائمة المراقبة.")
            return

        directions = []
        all_ok = True
        for frame in ANALYSIS_FRAMES:
            df = fetch_data_from_source(
                source=ACTIVE_DATA_SOURCE,
                symbol=asset_to_check_common,
                interval_or_timeframe=frame,
                count=CANDLE_COUNT_TO_FETCH,
                asset_config=asset_config_found
            )
            if df is None or df.empty: all_ok = False; break
            signal = analyze_single_frame(df, asset_to_check_common, frame) # analyze_single_frame معرفة في الأسفل
            if signal: directions.append(signal)
            else: all_ok = False; break
        
        if all_ok and len(directions) == len(ANALYSIS_FRAMES) and all(d == directions[0] for d in directions):
            msg = format_telegram_message(asset_to_check_common, directions[0], ANALYSIS_FRAMES) # format_telegram_message معرفة في الأسفل
            await update.message.reply_text(f"تحليل {asset_to_check_common}:\n{msg}", parse_mode="Markdown")
        elif not all_ok:
             await update.message.reply_text(f"تعذر الحصول على بيانات كافية أو إشارة واضحة لـ {asset_to_check_common}.")
        else:
            await update.message.reply_text(f"إشارات {asset_to_check_common} غير متوافقة: {directions}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء تحليل الأصل: {e}")


# --- دوال مساعدة (من الرد السابق) ---
def analyze_single_frame(data_df: pd.DataFrame, asset_common_name: str, timeframe: str) -> str | None:
    if data_df is None or data_df.empty: return None
    return get_single_signal_from_engine(data_df, timeframe=f"{asset_common_name} {timeframe}")

def generate_multiframe_signals() -> list:
    final_signals_for_trading = []
    for asset_info in ASSETS_TO_MONITOR:
        common_name = asset_info["COMMON_NAME"]
        directions_from_frames = []
        all_frames_ok = True
        for frame_tf in ANALYSIS_FRAMES:
            df_candles = fetch_data_from_source(
                source=ACTIVE_DATA_SOURCE,
                symbol=common_name,
                interval_or_timeframe=frame_tf,
                count=CANDLE_COUNT_TO_FETCH,
                asset_config=asset_info
            )
            if df_candles is None or df_candles.empty: all_frames_ok = False; break 
            signal_on_frame = analyze_single_frame(df_candles, common_name, frame_tf)
            if signal_on_frame: directions_from_frames.append(signal_on_frame)
            else: all_frames_ok = False; break
        
        if all_frames_ok and len(directions_from_frames) == len(ANALYSIS_FRAMES):
            first_signal = directions_from_frames[0]
            if all(s == first_signal for s in directions_from_frames):
                final_signals_for_trading.append({
                    "asset_common_name": common_name,
                    "asset_quotex_symbol": asset_info.get("QUOTEX_SYMBOL", common_name.replace("/", "")), 
                    "direction": first_signal
                })
    return final_signals_for_trading

def format_telegram_message(asset_name: str, direction: str, frames_list: list) -> str:
    now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    arrow = "📈 CALL" if direction == "call" else "📉 PUT"
    frames_str = " / ".join(frames_list)
    return f"🚨 **Trading Signal!** 🚨\nAsset: **{asset_name}**\nSignal: **{arrow}**\nSynced Frames: _{frames_str}_\nStrategy: EngineV2\nTime: {now_utc}"


# --- دالة التشغيل الرئيسية للبوت (التي تعمل في الخلفية) ---
async def background_analysis_loop(context: ContextTypes.DEFAULT_TYPE):
    global quotex_driver_instance, is_quotex_logged_in 

    iteration_num = 0
    while True:
        iteration_num += 1
        start_time_loop = time.time()
        
        try:
            generated_signals = generate_multiframe_signals() 
            
            if generated_signals:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔥 {len(generated_signals)} Signals Found! Processing...")
                for idx, signal_data in enumerate(generated_signals):
                    asset_name_common = signal_data["asset_common_name"]
                    asset_name_quotex = signal_data["asset_quotex_symbol"]
                    trade_direction = signal_data["direction"]
                    
                    tg_message = format_telegram_message(asset_name_common, trade_direction, ANALYSIS_FRAMES)
                    if context.bot and TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != "YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER":
                        try:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=tg_message, parse_mode="Markdown")
                        except Exception as e_tg_send:
                             print(f"Telegram send error in background loop: {e_tg_send}")
                    
                    if quotex_driver_instance:
                        if not is_quotex_logged_in:
                            is_quotex_logged_in = login_quotex(quotex_driver_instance, QUOTEX_EMAIL, QUOTEX_PASSWORD)
                        
                        if is_quotex_logged_in:
                            trade_executed = place_trade(
                                quotex_driver_instance,
                                asset=asset_name_quotex, direction=trade_direction,
                                amount=TRADE_AMOUNT, duration=TRADE_DURATION
                            )
                            if not trade_executed: is_quotex_logged_in = False 
                        # else: # لا حاجة لطباعة SIMULATED هنا إذا لم يتم تسجيل الدخول
                    # else: # لا حاجة لطباعة SIMULATED هنا إذا لم يكن الدرايفر متاحًا
                    
                    if idx < len(generated_signals) - 1: await asyncio.sleep(3)
            
        except Exception as e_main:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CRITICAL BACKGROUND LOOP ERROR] {type(e_main).__name__}: {e_main}")
            import traceback
            print(traceback.format_exc())

        loop_exec_time = time.time() - start_time_loop
        desired_cycle_interval = 60 
        sleep_duration = max(10, desired_cycle_interval - loop_exec_time)
        await asyncio.sleep(sleep_duration)

quotex_driver_instance = None
is_quotex_logged_in = False

async def post_init(application: Application) -> None:
    global quotex_driver_instance, is_quotex_logged_in
    # print("Bot post_init: Setting up Quotex browser and logging in...")
    try:
        quotex_driver_instance = setup_browser(headless=True)
        if quotex_driver_instance:
            is_quotex_logged_in = login_quotex(quotex_driver_instance, QUOTEX_EMAIL, QUOTEX_PASSWORD) # QUOTEX_EMAIL from config
            # if not is_quotex_logged_in: print("Bot post_init: Quotex login failed initially.")
        # else: print("Bot post_init: Quotex browser setup failed.")
    except Exception as e_setup:
        print(f"Bot post_init: Error during Quotex initial setup/login: {e_setup}")
        if quotex_driver_instance: close_browser(quotex_driver_instance)
        quotex_driver_instance = None; is_quotex_logged_in = False
    
    # تأكد من أن application.job_queue متاح إذا كنت تستخدمه (في v20+، create_task هو الأفضل للمهام الطويلة)
    asyncio.create_task(background_analysis_loop(application)) # تمرير application كـ context
    # print("Bot post_init: Background analysis loop scheduled.")


def main_telegram_app() -> None: # تم تغيير اسم الدالة
    print("✅ Initializing Telegram Bot Application...")
    
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER":
        print("CRITICAL: TELEGRAM_BOT_TOKEN is a placeholder. Bot cannot start.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("check", check_asset_command))
    
    print("Telegram Bot Application created. Starting polling...")
    application.run_polling()

    # --- منطق الإغلاق النظيف لـ Quotex ---
    global quotex_driver_instance 
    if quotex_driver_instance:
        print("\nShutting down: Closing Quotex browser...")
        close_browser(quotex_driver_instance)
    print("Bot shut down gracefully.")


if __name__ == "__main__":
    # هذا القسم يتم تنفيذه عند تشغيل الملف مباشرة
    # طباعة الإعدادات تتم هنا مرة واحدة
    print(f"Data Source: {ACTIVE_DATA_SOURCE} | Quotex User: {QUOTEX_EMAIL}")
    print(f"Assets: {[a['COMMON_NAME'] for a in ASSETS_TO_MONITOR]}")
    print(f"Timeframes: {ANALYSIS_FRAMES}")
    
    try:
        main_telegram_app() # استدعاء الدالة التي تشغل بوت تيليجرام
    except KeyboardInterrupt:
        print("\nBot manually interrupted by Ctrl+C.")
    # finally: # تم نقل منطق الإغلاق إلى نهاية main_telegram_app
        # print("Bot shutdown sequence from __main__ (if any cleanup needed).")
