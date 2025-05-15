# broker/quotex_executor.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time

# --- !!! قم بتحديث هذه المعرفات بدقة لتطابق واجهة Quotex الحالية !!! ---
LOGIN_URL = "https://qxbroker.com/en/sign-in" # أو الرابط الصحيح لمنطقتك/لغتك
EMAIL_INPUT_NAME = "email"
PASSWORD_INPUT_NAME = "password"
# مثال: عنصر يظهر بعد تسجيل الدخول (مثل رصيد الحساب أو اسم المستخدم)
LOGIN_SUCCESS_INDICATOR_XPATH = "//div[contains(@class,'header-avatar__photo') or contains(@class,'user-balance')]" # مثال مركب

ASSET_SELECTOR_BUTTON_CSS = "button.pair-button" # مثال من واجهة حديثة
ASSET_SEARCH_MODAL_CSS = "div.search-modal" # مثال للنافذة المنبثقة للبحث
ASSET_SEARCH_INPUT_CSS = "div.search-modal input[type='text']" # مثال لحقل البحث داخل النافذة
ASSET_SEARCH_RESULT_XPATH_TEMPLATE = "//div[contains(@class,'asset-item')]//div[contains(normalize-space(),'{}')]" # {} لاسم الأصل (EUR/USD)

TIME_SELECTOR_BUTTON_CSS = "button.time-button" # مثال
# مثال لزر مدة دقيقة واحدة (قد يكون النص "1:00" أو "1m" أو أيقونة)
DURATION_1M_BUTTON_XPATH = "//button[contains(@class,'time-item') and normalize-space(text())='1:00']" # مثال شائع لـ 1 دقيقة

AMOUNT_INPUT_CSS = "input.input-sum" # مثال
CALL_BUTTON_CSS = "button.deal-button--up" # مثال
PUT_BUTTON_CSS = "button.deal-button--down" # مثال
# -----------------------------------------------------------------------

def setup_browser(headless: bool = True, browser_type: str = "chrome") -> webdriver.Chrome | None:
    try:
        # print(f"Quotex: Setting up {browser_type} browser (headless={headless})...")
        if browser_type.lower() == "chrome":
            options = Options()
            if headless:
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36") # مثال User Agent
            driver = webdriver.Chrome(options=options)
            # print("Quotex: Chrome browser initialized.")
            return driver
        else:
            print(f"Quotex: Browser type '{browser_type}' not supported.")
            return None
    except Exception as e:
        print(f"Quotex: Error setting up browser: {e}")
        return None

def login_quotex(driver: webdriver.Chrome, email: str, password: str, timeout: int = 30) -> bool:
    if not driver: return False
    try:
        # print(f"Quotex: Navigating to login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.NAME, EMAIL_INPUT_NAME))
        ).send_keys(email)
        # print("Quotex: Email entered.")

        driver.find_element(By.NAME, PASSWORD_INPUT_NAME).send_keys(password)
        # print("Quotex: Password entered.")
        
        try:
            login_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and (contains(normalize-space(),'Sign in') or contains(normalize-space(),'Log In'))]"))
            )
            login_button.click()
            # print("Quotex: Clicked login button.")
        except:
            # print("Quotex: Login button not found by XPATH, attempting submit on password field.")
            driver.find_element(By.NAME, PASSWORD_INPUT_NAME).submit()

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, LOGIN_SUCCESS_INDICATOR_XPATH))
        )
        print("Quotex: Login successful.")
        return True
    except TimeoutException:
        print("Quotex: Timeout during login.")
        # driver.save_screenshot("quotex_login_timeout.png")
    except Exception as e:
        print(f"Quotex: Error during login: {e}")
    return False

def select_asset(driver: webdriver.Chrome, asset_name_quotex: str, timeout: int = 15) -> bool:
    if not driver: return False
    try:
        # print(f"Quotex: Selecting asset '{asset_name_quotex}'...")
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ASSET_SELECTOR_BUTTON_CSS))
        ).click()

        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ASSET_SEARCH_MODAL_CSS))
        )
        
        search_input = driver.find_element(By.CSS_SELECTOR, ASSET_SEARCH_INPUT_CSS)
        search_input.clear()
        search_input.send_keys(asset_name_quotex) # Quotex عادة لا تستخدم "/" في البحث
        time.sleep(0.5) 

        # يجب أن يكون asset_name_quotex هو النص المعروض في القائمة (مثل "EUR/USD" أو "EURUSD")
        asset_xpath = ASSET_SEARCH_RESULT_XPATH_TEMPLATE.format(asset_name_quotex)
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, asset_xpath))
        ).click()
        # print(f"Quotex: Asset '{asset_name_quotex}' selected.")
        time.sleep(0.5) 
        return True
    except Exception as e:
        print(f"Quotex: Error selecting asset '{asset_name_quotex}': {type(e).__name__} - {e}")
    return False

def set_trade_duration(driver: webdriver.Chrome, duration_str: str, timeout: int = 10) -> bool:
    if not driver: return False
    # هذا الجزء يعتمد بشدة على كيفية اختيار المدة في Quotex
    # قد يكون هناك أزرار محددة ("1m", "5m") أو قائمة منسدلة أو حقل إدخال
    # المثال التالي يفترض وجود زر محدد لـ 1m (أو ما يعادله "1:00")
    try:
        # print(f"Quotex: Setting trade duration to '{duration_str}'...")
        # انقر لفتح قائمة اختيار المدة إذا كانت موجودة
        # WebDriverWait(driver, timeout).until(
        #     EC.element_to_be_clickable((By.CSS_SELECTOR, TIME_SELECTOR_BUTTON_CSS))
        # ).click()
        
        # اختر المدة (هذا مثال لـ 1m، قد تحتاج لتعديله)
        if duration_str == "1m": # أو أي مدة أخرى تدعمها
            duration_button_xpath = DURATION_1M_BUTTON_XPATH # مثال لـ 1m
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, duration_button_xpath))
            ).click()
            # print(f"Quotex: Duration '{duration_str}' set.")
            return True
        else:
            print(f"Quotex: Duration '{duration_str}' not explicitly supported by this function's example. Please adapt.")
            return False # أو حاول إدخالها بطريقة أخرى إذا كانت الواجهة تسمح
            
    except Exception as e:
        print(f"Quotex: Error setting duration '{duration_str}': {e}")
    return False

def set_trade_amount(driver: webdriver.Chrome, amount: int, timeout: int = 10) -> bool:
    if not driver: return False
    try:
        # print(f"Quotex: Setting trade amount to {amount}...")
        amount_field = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, AMOUNT_INPUT_CSS))
        )
        # طريقة موثوقة لمسح الحقل وإدخال القيمة
        amount_field.click() # انقر أولاً لتنشيط الحقل
        driver.execute_script(f"arguments[0].value = '{str(amount)}'; arguments[0].dispatchEvent(new Event('input'));", amount_field)
        # print(f"Quotex: Amount {amount} set.")
        time.sleep(0.2) # انتظر قليلاً لتحديث الواجهة
        return True
    except Exception as e:
        print(f"Quotex: Error setting amount {amount}: {e}")
    return False

def place_trade(driver: webdriver.Chrome, asset: str, direction: str, amount: int, duration: str, timeout: int = 15) -> bool:
    if not driver: return False
    try:
        # print(f"\nQuotex: Attempting trade -> {asset}, {direction.upper()}, Amt: {amount}, Dur: {duration}")
        
        if not select_asset(driver, asset, timeout): # asset هو asset_quotex_symbol
            return False
        
        # Quotex عادة ما يكون لديها أزرار مدة ثابتة. مثال 1m
        if duration == "1m": # أو أي مدة أخرى تريد دعمها
            if not set_trade_duration(driver, "1m", timeout): # يستخدم الزر المحدد لـ 1m
                 print(f"Quotex: Failed to set 1m duration. Trade aborted.")
                 return False
        else:
            print(f"Quotex: Duration '{duration}' not directly supported for automated click. Trade aborted.")
            return False

        if not set_trade_amount(driver, amount, timeout):
            return False

        button_css = CALL_BUTTON_CSS if direction.lower() == "call" else PUT_BUTTON_CSS
        trade_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, button_css))
        )
        trade_button.click()
        # print(f"Quotex: {direction.upper()} button clicked for {asset}.")
        time.sleep(0.5) # انتظار قصير بعد النقر
        # هنا يمكنك محاولة التحقق من أن الصفقة ظهرت في قائمة الصفقات المفتوحة
        # هذا الجزء معقد ويعتمد على واجهة Quotex
        print(f"Quotex: Trade for {asset} - {direction.upper()} presumed placed.")
        return True
        
    except Exception as e:
        print(f"Quotex: Error placing trade for {asset}: {type(e).__name__} - {e}")
    return False

def close_browser(driver: webdriver.Chrome | None):
    if driver:
        try:
            # print("Quotex: Closing browser...")
            driver.quit()
            # print("Quotex: Browser closed.")
        except Exception as e:
            print(f"Quotex: Error closing browser: {e}")