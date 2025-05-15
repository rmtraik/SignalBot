# main_bot.py (مع تعديلات ليصبح بوت تيليجرام تفاعلي)

# ... (جميع الاستيرادات والإعدادات كما في الرد السابق) ...
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio # للتشغيل غير المتزامن

# --- (جميع دوال التحليل، جلب البيانات، إرسال الإشعارات، Quotex كما هي) ---
# analyze_single_frame, generate_multiframe_signals, format_telegram_message,
# send_to_telegram (قد تحتاج إلى تعديل طفيف لتستخدم context.bot)
# ودوال Quotex executor

# --- معالجات أوامر تيليجرام ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يرسل رسالة عندما يتم إصدار الأمر /start."""
    user = update.effective_user
    await update.message.reply_html(
        rf"أهلاً {user.mention_html()}! أنا بوت  zitro تحليل الإشارات. حاليًا أراقب تلقائيًا.",
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعرض حالة البوت."""
    # يمكنك إضافة المزيد من التفاصيل هنا
    status_message = f"""
    📊 **حالة البوت** 📊
    مصدر البيانات النشط: {ACTIVE_DATA_SOURCE}
    الأصول المراقبة: {[a['COMMON_NAME'] for a in ASSETS_TO_MONITOR]}
    الأطر الزمنية للتحليل: {ANALYSIS_FRAMES}
    """
    await update.message.reply_text(status_message, parse_mode="Markdown")

async def check_asset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يحلل أصل معين عند الطلب ويرسل الإشارة (بدون تداول)."""
    try:
        asset_to_check_common = context.args[0].upper() # EUR/USD أو BTC/USD
        await update.message.reply_text(f"🔍 جاري تحليل {asset_to_check_common} على الأطر الزمنية {ANALYSIS_FRAMES}...")

        asset_config_found = next((a for a in ASSETS_TO_MONITOR if a["COMMON_NAME"] == asset_to_check_common), None)
        if not asset_config_found:
            await update.message.reply_text(f"لم يتم العثور على الأصل {asset_to_check_common} في قائمة المراقبة المعدة مسبقًا.")
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
            if df is None or df.empty:
                all_ok = False
                break
            signal = analyze_single_frame(df, asset_to_check_common, frame)
            if signal:
                directions.append(signal)
            else:
                all_ok = False
                break
        
        if all_ok and len(directions) == len(ANALYSIS_FRAMES) and all(d == directions[0] for d in directions):
            msg = format_telegram_message(asset_to_check_common, directions[0], ANALYSIS_FRAMES)
            await update.message.reply_text(f"تحليل {asset_to_check_common}:\n{msg}", parse_mode="Markdown")
        elif not all_ok:
             await update.message.reply_text(f"تعذر الحصول على بيانات كافية أو إشارة واضحة لـ {asset_to_check_common} على جميع الأطر.")
        else:
            await update.message.reply_text(f"إشارات {asset_to_check_common} غير متوافقة عبر الأطر: {directions}")

    except (IndexError, ValueError):
        await update.message.reply_text("الاستخدام: /check <ASSET_SYMBOL> (مثال: /check EUR/USD)")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء تحليل الأصل: {e}")


# --- دالة التشغيل الرئيسية للبوت (التي تعمل في الخلفية) ---
async def background_analysis_loop(context: ContextTypes.DEFAULT_TYPE):
    """الحلقة الرئيسية للتحليل الدوري وإرسال الإشارات والتداول."""
    global quotex_driver_instance, is_quotex_logged_in # استخدام المتغيرات العامة

    iteration_num = 0
    while True:
        iteration_num += 1
        # print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background Iteration {iteration_num}...")
        start_time_loop = time.time()
        
        try:
            generated_signals = generate_multiframe_signals() # هذه الدالة متزامنة، قد تحتاج لتشغيلها في منفذ إذا كانت بطيئة جدا
            
            if generated_signals:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔥 {len(generated_signals)} Signals Found! Processing...")
                for idx, signal_data in enumerate(generated_signals):
                    asset_name_common = signal_data["asset_common_name"]
                    asset_name_quotex = signal_data["asset_quotex_symbol"]
                    trade_direction = signal_data["direction"]
                    
                    # print(f"  Signal {idx+1}: {asset_name_common} -> {trade_direction.upper()}")
                    
                    tg_message = format_telegram_message(asset_name_common, trade_direction, ANALYSIS_FRAMES)
                    # إرسال الرسالة باستخدام context.bot
                    if context.bot and TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != "zitro_signal":
                        try:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=tg_message, parse_mode="Markdown")
                        except Exception as e_tg_send:
                             print(f"Telegram send error in background loop: {e_tg_send}")
                    
                    # --- منطق التداول على Quotex (كما كان، مع تعديل بسيط لاستخدام المتغيرات العامة) ---
                    if quotex_driver_instance:
                        if not is_quotex_logged_in:
                            print("Background: Attempting to re-login to Quotex...")
                            is_quotex_logged_in = login_quotex(quotex_driver_instance, QUOTEX_EMAIL, QUOTEX_PASSWORD)
                        
                        if is_quotex_logged_in:
                            print(f"    Background: Attempting Quotex trade for {asset_name_quotex}...")
                            trade_executed = place_trade(
                                quotex_driver_instance,
                                asset=asset_name_quotex, direction=trade_direction,
                                amount=TRADE_AMOUNT, duration=TRADE_DURATION
                            )
                            if not trade_executed:
                                 print(f"    Background: Quotex trade for {asset_name_quotex} FAILED.")
                                 is_quotex_logged_in = False 
                        else:
                            print(f"    Background: SIMULATED Quotex trade for {asset_name_quotex} (Not logged in).")
                    else:
                        print(f"    Background: SIMULATED Quotex trade for {asset_name_quotex} (Driver not available).")
                    
                    if idx < len(generated_signals) - 1: await asyncio.sleep(3) # استخدام asyncio.sleep
            
        except Exception as e_main:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CRITICAL BACKGROUND LOOP ERROR] {type(e_main).__name__}: {e_main}")
            import traceback
            print(traceback.format_exc())

        loop_exec_time = time.time() - start_time_loop
        desired_cycle_interval = 60 
        sleep_duration = max(10, desired_cycle_interval - loop_exec_time)
        await asyncio.sleep(sleep_duration) # استخدام asyncio.sleep

# --- متغيرات عامة لـ Quotex (ليست الطريقة المثالية، ولكنها أبسط للبدء) ---
quotex_driver_instance = None
is_quotex_logged_in = False

async def post_init(application: Application) -> None:
    """يتم تشغيله بعد تهيئة التطبيق وقبل بدء الجلب."""
    global quotex_driver_instance, is_quotex_logged_in
    print("Bot post_init: Setting up Quotex browser and logging in...")
    try:
        quotex_driver_instance = setup_browser(headless=True)
        if quotex_driver_instance:
            is_quotex_logged_in = login_quotex(quotex_driver_instance, QUOTEX_EMAIL, QUOTEX_PASSWORD)
            if not is_quotex_logged_in:
                print("Bot post_init: Quotex login failed initially.")
        else:
            print("Bot post_init: Quotex browser setup failed.")
    except Exception as e_setup:
        print(f"Bot post_init: Error during Quotex initial setup/login: {e_setup}")
        if quotex_driver_instance: close_browser(quotex_driver_instance)
        quotex_driver_instance = None
        is_quotex_logged_in = False

    # جدولة مهمة الخلفية
    asyncio.create_task(background_analysis_loop(application))
    print("Bot post_init: Background analysis loop scheduled.")


def main() -> None:
    """يبدأ البوت."""
    print("✅ Initializing Telegram Bot Application...")
    
    # --- التحقق من الإعدادات الأساسية ---
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER":
        print("CRITICAL: TELEGRAM_BOT_TOKEN is a placeholder. Bot cannot start.")
        return
    # يمكنك إضافة المزيد من عمليات التحقق هنا

    # إنشاء Application وتمرير توكن البوت
    # استخدم context_types لسهولة الوصول إلى context.bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("check", check_asset_command))
    # يمكنك إضافة المزيد من المعالجات هنا

    print("Telegram Bot Application created. Starting polling...")
    # تشغيل البوت حتى يضغط المستخدم Ctrl-C
    application.run_polling()

    # --- منطق الإغلاق النظيف لـ Quotex ---
    # هذا الجزء سيتم الوصول إليه فقط عند إيقاف البوت (مثل Ctrl+C)
    global quotex_driver_instance # الوصول للمتغير العام
    if quotex_driver_instance:
        print("\nShutting down: Closing Quotex browser...")
        close_browser(quotex_driver_instance)
    print("Bot shut down gracefully.")


if __name__ == "__main__":
    # --- إعدادات عامة (من الرد السابق) ---
    print(f"Data Source: {ACTIVE_DATA_SOURCE} | Quotex User: {QUOTEX_EMAIL}")
    print(f"Assets: {[a['COMMON_NAME'] for a in ASSETS_TO_MONITOR]}")
    print(f"Timeframes: {ANALYSIS_FRAMES}")
    
    main()
