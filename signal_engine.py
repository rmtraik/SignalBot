import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volume import OnBalanceVolumeIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from strategy.candle_patterns import detect_candlestick_patterns

def generate_signals(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    df = df.copy()

    df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    df['ema50'] = EMAIndicator(df['close'], window=50).ema_indicator()
    df['trend_up'] = df['ema20'] > df['ema50']

    df['tenkan'] = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
    df['ichimoku_up'] = df['close'] > df['tenkan']

    df['rsi'] = RSIIndicator(df['close'], window=9).rsi()
    macd = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_bullish'] = df['macd_line'] > df['macd_signal']

    stochastic = StochasticOscillator(df['high'], df['low'], df['close'], window=5, smooth_window=3)
    df['stoch'] = stochastic.stoch()

    df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    df['obv_trend'] = df['obv'].rolling(20).mean() > df['obv'].rolling(50).mean()

    boll = BollingerBands(df['close'], window=20, window_dev=2)
    df['boll_lower'] = boll.bollinger_lband()
    df['boll_upper'] = boll.bollinger_hband()
    df['price_touches_lower'] = df['close'] <= df['boll_lower']
    df['price_touches_upper'] = df['close'] >= df['boll_upper']

    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()

    patterns = detect_candlestick_patterns(df)
    df = pd.concat([df, patterns], axis=1)

    df['buy_signal'] = (
        df['trend_up'] & df['ichimoku_up'] &
        (df['rsi'] < 70) & df['macd_bullish'] &
        (df['stoch'].between(20, 80)) & df['obv_trend'] &
        df['price_touches_lower'] &
        (df['bullish_engulfing'] | df['hammer'] | df['morning_star'] | df['three_white_soldiers'])
    )

    df['sell_signal'] = (
        (df['ema20'] < df['ema50']) & (df['close'] < df['tenkan']) &
        (df['rsi'] > 30) & (df['macd_line'] < df['macd_signal']) &
        (df['stoch'].between(20, 80)) & (~df['obv_trend']) &
        df['price_touches_upper'] &
        (df['bearish_engulfing'] | df['shooting_star'] | df['evening_star'] | df['three_black_crows'])
    )

    df['signal_reason'] = ""  # لم نعد نعرض السبب

    return df[['buy_signal', 'sell_signal', 'signal_reason']]
