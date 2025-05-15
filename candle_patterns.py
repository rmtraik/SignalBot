import pandas as pd
import numpy as np # لاستخدامه في np.nan عند الحاجة أو للعمليات الرقمية

def detect_candlestick_patterns(
    df_input: pd.DataFrame,
    doji_threshold: float = 0.1,
    hammer_body_max_ratio: float = 0.4,
    hammer_lower_shadow_min_ratio: float = 0.5,
    hammer_upper_shadow_max_ratio: float = 0.2,
    # يمكنك إضافة المزيد من المعلمات هنا إذا لزم الأمر
) -> pd.DataFrame:
    
    # التأكد من أن الأعمدة المطلوبة موجودة
    required_columns = ['open', 'high', 'low', 'close']
    if not all(col in df_input.columns for col in required_columns):
        print("Error: DataFrame is missing one or more required OHLC columns for pattern detection.")
        # إرجاع DataFrame فارغ بنفس الأعمدة المتوقعة لتجنب أخطاء لاحقة
        empty_patterns = pd.DataFrame(columns=[
            'bullish_engulfing', 'bearish_engulfing', 'hammer', 'shooting_star', 'doji',
            'morning_star', 'evening_star', 'three_white_soldiers', 'three_black_crows'
        ], index=df_input.index)
        return empty_patterns.fillna(False)

    df = df_input.copy()

    # حساب خصائص الشمعة الأساسية
    # استخدام np.abs لضمان أن الجسم دائمًا موجب أو صفر
    candle_body_size = np.abs(df['close'] - df['open'])
    candle_total_range = df['high'] - df['low']
    
    # معالجة حالة candle_total_range == 0 لتجنب القسمة على صفر
    # إذا كان النطاق صفرًا (شمعة خطية)، فالنسب ستكون NaN أو inf.
    # يمكننا تعيينها إلى قيمة آمنة (مثل 1) أو التعامل معها بشكل خاص.
    # هنا، سنقوم بتعبئة NaNs الناتجة لاحقًا.
    candle_total_range_safe = candle_total_range.replace(0, np.nan) # استبدل 0 بـ NaN لتجنب القسمة على صفر

    upper_shadow = df['high'] - df[['close', 'open']].max(axis=1)
    lower_shadow = df[['close', 'open']].min(axis=1) - df['low']

    # --- تعريفات الأنماط ---

    # 1. Doji
    # الجسم صغير جدًا مقارنة بالنطاق الكلي
    df['doji'] = (candle_body_size / candle_total_range_safe) < doji_threshold

    # 2. Hammer (مطرقة)
    # جسم صغير، ظل سفلي طويل، ظل علوي قصير
    is_hammer_shape = (
        (candle_body_size / candle_total_range_safe < hammer_body_max_ratio) &
        (lower_shadow / candle_total_range_safe > hammer_lower_shadow_min_ratio) &
        (upper_shadow / candle_total_range_safe < hammer_upper_shadow_max_ratio)
    )
    # المطرقة تحدث عادة في اتجاه هابط (هذا شرط إضافي، قد يكون اختياريًا حسب التعريف)
    # trend_down_prev = df['close'].shift(1) < df['open'].shift(1) # مثال لشرط اتجاه
    df['hammer'] = is_hammer_shape # & trend_down_prev (إذا أردت إضافة شرط الاتجاه)

    # 3. Shooting Star (شهاب)
    # جسم صغير، ظل علوي طويل، ظل سفلي قصير
    is_shooting_star_shape = (
        (candle_body_size / candle_total_range_safe < hammer_body_max_ratio) & # نفس نسب الجسم
        (upper_shadow / candle_total_range_safe > hammer_lower_shadow_min_ratio) & # ظل علوي طويل
        (lower_shadow / candle_total_range_safe < hammer_upper_shadow_max_ratio)  # ظل سفلي قصير
    )
    # الشهاب يحدث عادة في اتجاه صاعد (شرط إضافي اختياري)
    # trend_up_prev = df['close'].shift(1) > df['open'].shift(1) # مثال لشرط اتجاه
    df['shooting_star'] = is_shooting_star_shape # & trend_up_prev (إذا أردت إضافة شرط الاتجاه)

    # 4. Bullish Engulfing (ابتلاع شرائي)
    # الشمعة الحالية صاعدة تبتلع جسم الشمعة الهابطة السابقة
    df['bullish_engulfing'] = (
        (df['close'].shift(1) < df['open'].shift(1)) & # الشمعة السابقة هابطة
        (df['close'] > df['open']) &                  # الشمعة الحالية صاعدة
        (df['open'] < df['close'].shift(1)) &         # افتتاح الحالية أقل من إغلاق السابقة
        (df['close'] > df['open'].shift(1))           # إغلاق الحالية أعلى من افتتاح السابقة
    )

    # 5. Bearish Engulfing (ابتلاع بيعي)
    # الشمعة الحالية هابطة تبتلع جسم الشمعة الصاعدة السابقة
    df['bearish_engulfing'] = (
        (df['close'].shift(1) > df['open'].shift(1)) & # الشمعة السابقة صاعدة
        (df['close'] < df['open']) &                  # الشمعة الحالية هابطة
        (df['open'] > df['close'].shift(1)) &         # افتتاح الحالية أعلى من إغلاق السابقة
        (df['close'] < df['open'].shift(1))           # إغلاق الحالية أقل من افتتاح السابقة
    )
    
    # 6. Morning Star (نجمة الصباح)
    # شمعة هابطة طويلة، تليها شمعة ذات جسم صغير (Doji أو Hammer أو Spinning Top) مع فجوة للأسفل،
    # ثم شمعة صاعدة تغلق جيدًا داخل جسم الشمعة الأولى.
    # (الشرط الأصلي كان جيدًا، يمكن تبسيطه قليلاً بالاعتماد على 'doji' و 'hammer' المحسوبة)
    prev_is_bearish = df['close'].shift(2) < df['open'].shift(2)
    middle_is_small_body_star = (df['doji'].shift(1) | df['hammer'].shift(1)) # يمكن إضافة Spinning Top هنا
    current_is_bullish = df['close'] > df['open']
    current_closes_in_first_body = df['close'] > (df['open'].shift(2) + df['close'].shift(2)) / 2
    
    df['morning_star'] = prev_is_bearish & middle_is_small_body_star & \
                         current_is_bullish & current_closes_in_first_body

    # 7. Evening Star (نجمة المساء)
    # عكس نجمة الصباح
    prev_is_bullish = df['close'].shift(2) > df['open'].shift(2)
    middle_is_small_body_star_evening = (df['doji'].shift(1) | df['shooting_star'].shift(1)) # أو Spinning Top
    current_is_bearish = df['close'] < df['open']
    current_closes_in_first_body_evening = df['close'] < (df['open'].shift(2) + df['close'].shift(2)) / 2

    df['evening_star'] = prev_is_bullish & middle_is_small_body_star_evening & \
                         current_is_bearish & current_closes_in_first_body_evening

    # 8. Three White Soldiers (ثلاثة جنود بيض)
    # ثلاث شمعات صاعدة متتالية، كل واحدة تغلق أعلى من السابقة،
    # وافتتاح كل شمعة يكون ضمن جسم الشمعة السابقة.
    # (الشرط الأصلي كان جيدًا، يمكن إضافة شرط الافتتاح)
    is_bullish_candle = df['close'] > df['open']
    prev_is_bullish_candle = df['close'].shift(1) > df['open'].shift(1)
    prev_prev_is_bullish_candle = df['close'].shift(2) > df['open'].shift(2)

    closes_are_higher = (df['close'] > df['close'].shift(1)) & \
                        (df['close'].shift(1) > df['close'].shift(2))
    
    # شرط الافتتاح (اختياري ولكنه يقوي النمط)
    # open_in_prev_body = (df['open'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1)) & \
    #                     (df['open'].shift(1) > df['open'].shift(2)) & (df['open'].shift(1) < df['close'].shift(2))

    df['three_white_soldiers'] = (
        is_bullish_candle & prev_is_bullish_candle & prev_prev_is_bullish_candle &
        closes_are_higher # & open_in_prev_body (إذا أضفت شرط الافتتاح)
    )

    # 9. Three Black Crows (ثلاثة غربان سود)
    # عكس الثلاثة جنود البيض
    is_bearish_candle = df['close'] < df['open']
    prev_is_bearish_candle = df['close'].shift(1) < df['open'].shift(1)
    prev_prev_is_bearish_candle = df['close'].shift(2) < df['open'].shift(2)

    closes_are_lower = (df['close'] < df['close'].shift(1)) & \
                       (df['close'].shift(1) < df['close'].shift(2))

    # شرط الافتتاح (اختياري)
    # open_in_prev_body_bearish = (df['open'] < df['open'].shift(1)) & (df['open'] > df['close'].shift(1)) & \
    #                             (df['open'].shift(1) < df['open'].shift(2)) & (df['open'].shift(1) > df['close'].shift(2))
                                
    df['three_black_crows'] = (
        is_bearish_candle & prev_is_bearish_candle & prev_prev_is_bearish_candle &
        closes_are_lower # & open_in_prev_body_bearish
    )

    # تحديد الأعمدة المراد إرجاعها
    pattern_columns = [
        'bullish_engulfing', 'bearish_engulfing',
        'hammer', 'shooting_star', 'doji',
        'morning_star', 'evening_star',
        'three_white_soldiers', 'three_black_crows'
    ]
    
    # ملء أي قيم NaN (ناتجة عن shift أو قسمة على صفر) بـ False
    # هذا مهم لأن النمط لا يمكن أن يكون صحيحًا إذا كانت بياناته المصدر NaN
    for col in pattern_columns:
        if col in df.columns: # تأكد أن العمود تم إنشاؤه
            df[col] = df[col].fillna(False)
        else: # إذا لم يتم إنشاء العمود لسبب ما (نادر)، قم بإنشائه كـ False
            df[col] = False


    return df[pattern_columns]

# --- مثال للاستخدام (للاختبار فقط) ---
if __name__ == '__main__':
    # إنشاء DataFrame وهمي للاختبار
    data = {
        'open':   [10, 12, 11, 13, 15, 14, 13, 12, 10, 11, 10.5, 10.8, 9],
        'high':   [11, 13, 12, 14, 16, 15, 14, 13, 11, 12, 11.0, 11.0, 10],
        'low':    [9,  11, 10, 12, 14, 13, 12, 11, 9,  10, 10.0, 10.2, 8],
        'close':  [10.5,12.5,10.5,13.5,15.5,13.5,12.5,11.5,10.5,11.5,10.8, 10.3, 8.5],
        'volume': [100,120,110,130,150,140,130,120,100,110,90, 95, 120] 
    }
    sample_df = pd.DataFrame(data)
    sample_df.index = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', 
                                      '2023-01-05', '2023-01-06', '2023-01-07', '2023-01-08',
                                      '2023-01-09', '2023-01-10', '2023-01-11', '2023-01-12', '2023-01-13'])

    print("Original DataFrame:")
    print(sample_df)
    
    patterns_result = detect_candlestick_patterns(sample_df)
    print("\nDetected Patterns (True if pattern found for that candle):")
    print(patterns_result)

    # طباعة الأنماط التي تم العثور عليها فقط
    print("\nCandles with detected patterns:")
    for pattern_name in patterns_result.columns:
        detected_on_candles = patterns_result[patterns_result[pattern_name]].index.to_list()
        if detected_on_candles:
            print(f"  {pattern_name}: detected on {detected_on_candles}")