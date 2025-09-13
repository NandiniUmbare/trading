import configparser
import time
import logging
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
from kiteconnect import KiteConnect, KiteException
import numpy as np
import os

# --- Configuration ---
CONFIG_FILE = 'config.ini'
LOG_FILE = 'intraday_avwap_bot.log'
UNIVERSE_FILE = 'nifty500.txt'

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE),
                              logging.StreamHandler()])

def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config

def save_access_token(config, access_token):
    config['KITE']['ACCESS_TOKEN'] = access_token
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    logging.info("Access token saved to config file.")

# --- Kite Connect Authentication ---
def kite_login(config):
    try:
        api_key = config['KITE']['API_KEY']
        api_secret = config['KITE']['API_SECRET']
        access_token = config['KITE'].get('ACCESS_TOKEN')
        kite = KiteConnect(api_key=api_key)
        if access_token:
            try:
                kite.set_access_token(access_token)
                kite.profile()
                logging.info("Logged in successfully using saved access token.")
                return kite
            except KiteException:
                logging.warning("Saved token invalid. Attempting full login.")

        print("Please open this URL and authorize the app:", kite.login_url())
        request_token = input("Enter the request_token from the redirect URL: ")
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        save_access_token(config, access_token)
        logging.info("Login successful. New access token saved.")
        return kite
    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        return None

# --- Core Trading Logic ---
def get_stocks_to_trade(kite, stock_list, liquidity_threshold):
    try:
        instruments = [f"NSE:{stock}" for stock in stock_list]
        # Fetch quotes in chunks to avoid hitting API limits
        chunk_size = 200
        quotes = {}
        for i in range(0, len(instruments), chunk_size):
            chunk = instruments[i:i+chunk_size]
            quotes.update(kite.quote(chunk))
            time.sleep(0.5)

        if not quotes:
            logging.error("Could not fetch quotes for the stock list.")
            return []

        advances = 0
        declines = 0
        stock_performance = []

        for stock in stock_list:
            instrument = f"NSE:{stock}"
            if instrument in quotes and quotes[instrument]['last_price'] > 0:
                ohlc = quotes[instrument]['ohlc']
                if ohlc['open'] > 0:
                    # Check liquidity
                    ltp = quotes[instrument]['last_price']
                    volume = quotes[instrument]['volume']
                    traded_value = ltp * volume
                    if traded_value < liquidity_threshold:
                        continue # Skip illiquid stocks

                    change = (ltp / ohlc['open'] - 1) * 100
                    stock_performance.append({'symbol': stock, 'change': change})
                    if change > 0:
                        advances += 1
                    else:
                        declines += 1

        logging.info(f"Market Sentiment (Nifty 500): Advances: {advances}, Declines: {declines}")

        sorted_stocks = sorted(stock_performance, key=lambda x: x['change'], reverse=True)

        if advances > declines:
            logging.info("Bullish sentiment detected. Selecting top 2 gainers.")
            return [s['symbol'] for s in sorted_stocks[:2]]
        else:
            logging.info("Bearish sentiment detected. Selecting top 2 losers.")
            return [s['symbol'] for s in sorted_stocks[-2:]]

    except Exception as e:
        logging.error(f"Error getting stocks to trade: {e}")
        return []

def fetch_and_calculate_avwap(kite, stock, std_dev_multiplier):
    try:
        instrument_token = kite.ltp(f"NSE:{stock}")[f"NSE:{stock}"]["instrument_token"]
        from_date = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        to_date = datetime.now()
        records = kite.historical_data(instrument_token, from_date, to_date, "5minute")

        if not records:
            logging.warning(f"No historical data for {stock}")
            return None

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])

        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['tpv'] = df['tp'] * df['volume']
        df['cum_tpv'] = df['tpv'].cumsum()
        df['cum_volume'] = df['volume'].cumsum()
        df['avwap'] = df['cum_tpv'] / df['cum_volume']

        df['sq_diff'] = ((df['close'] - df['avwap']) ** 2)
        df['cum_sq_diff'] = df['sq_diff'].cumsum()
        df['mean_sq_err'] = df['cum_sq_diff'] / (np.arange(len(df)) + 1)
        df['std_dev'] = np.sqrt(df['mean_sq_err'])

        df['upper_band'] = df['avwap'] + (df['std_dev'] * std_dev_multiplier)
        df['lower_band'] = df['avwap'] - (df['std_dev'] * std_dev_multiplier)

        return df.iloc[-1]

    except Exception as e:
        logging.error(f"Failed to calculate AVWAP for {stock}: {e}")
        return None

def place_mis_order(kite, tradingsymbol, transaction_type, quantity):
    # ... (rest of the function remains the same)

def get_next_market_open_sleep_duration():
    # ... (function remains the same)

# --- Main Bot Loop ---
def run_bot():
    config = load_config()
    kite = kite_login(config)

    if not kite: return

    bot_config = config['INTRADAY_AVWAP_BOT']
    try:
        with open(UNIVERSE_FILE, 'r') as f:
            stock_list = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"{UNIVERSE_FILE} not found. Exiting.")
        return

    capital_per_trade = float(bot_config['CAPITAL_PER_TRADE'])
    daily_stop_loss = float(bot_config['DAILY_STOP_LOSS'])
    std_dev_multiplier = float(bot_config['AVWAP_STDDEV_MULTIPLIER'])
    liquidity_threshold = float(bot_config['LIQUIDITY_THRESHOLD'])

    stocks_to_trade = []
    traded_stocks_today = set()
    trading_halted = False

    while True:
        try:
            now = datetime.now()
            market_open_time = dt_time(9, 15)
            market_close_time = dt_time(15, 15)
            select_time = dt_time(9, 30)

            if now.time() > market_close_time or now.time() < market_open_time:
                # ... (logic remains the same)

            if trading_halted:
                time.sleep(300)
                continue

            if not stocks_to_trade and now.time() >= select_time:
                stocks_to_trade = get_stocks_to_trade(kite, stock_list, liquidity_threshold)
                logging.info(f"Selected stocks to trade for the day: {stocks_to_trade}")

            if not stocks_to_trade:
                logging.info("Waiting until 9:30 AM to select stocks.")
                time.sleep(60)
                continue

            positions = kite.positions()['net']
            open_positions = {p['tradingsymbol']: p for p in positions if p['product'] == 'MIS' and p['quantity'] != 0}

            for stock in stocks_to_trade:
                if stock in traded_stocks_today and stock not in open_positions: continue

                latest_data = fetch_and_calculate_avwap(kite, stock, std_dev_multiplier)
                if latest_data is None: continue

                ltp = latest_data['close']

                if stock not in open_positions:
                    if ltp > latest_data['upper_band']:
                        qty = int(capital_per_trade / ltp)
                        if qty > 0:
                            place_mis_order(kite, stock, kite.TRANSACTION_TYPE_BUY, qty)
                            traded_stocks_today.add(stock)
                    elif ltp < latest_data['lower_band']:
                        qty = int(capital_per_trade / ltp)
                        if qty > 0:
                            place_mis_order(kite, stock, kite.TRANSACTION_TYPE_SELL, qty)
                            traded_stocks_today.add(stock)
                else:
                    pos = open_positions[stock]
                    if pos['quantity'] > 0 and ltp < latest_data['lower_band']:
                        place_mis_order(kite, stock, kite.TRANSACTION_TYPE_SELL, abs(pos['quantity']))
                    elif pos['quantity'] < 0 and ltp > latest_data['upper_band']:
                         place_mis_order(kite, stock, kite.TRANSACTION_TYPE_BUY, abs(pos['quantity']))

            pnl = kite.pnl()
            if pnl and 'realised' in pnl:
                daily_pnl = sum(p['pnl'] for p in pnl['realised'])
                if daily_pnl <= daily_stop_loss:
                    logging.critical(f"DAILY STOP LOSS HIT! P&L: {daily_pnl:.2f}. Halting trades.")
                    trading_halted = True

            time.sleep(300)

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            time.sleep(60)

if __name__ == '__main__':
    run_bot()
