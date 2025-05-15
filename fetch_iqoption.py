# data_fetcher.py
# ... (الاستيرادات كما كانت) ...

# --- إعدادات من ملف التكوين ---
try:
    # تم تحديث هذا ليطابق الأسماء الجديدة في api_keys_config.py
    from config.api_keys_config import TWELVEDATA_API_KEY, IQ_OPTION_EMAIL, IQ_OPTION_PASSWORD
    print("Data_fetcher: Successfully loaded API keys from config.")
except ImportError:
    print("Data_fetcher Warning: config/api_keys_config.py not found. Using placeholders.")
    TWELVEDATA_API_KEY = "b7ef1a4efe984f93a02cf9a5653e3621" # هذا يجب أن يكون من api_keys_config
    IQ_OPTION_EMAIL = "rmtraik@gmail.com"
    IQ_OPTION_PASSWORD = "0668526953"

# ... (بقية دوال _fetch_iq_candles_internal و _fetch_twelvedata_candles_internal كما هي) ...
# ... (دالة fetch_data_from_source كما هي) ...

# ... (قسم if __name__ == '__main__': كما هو) ...