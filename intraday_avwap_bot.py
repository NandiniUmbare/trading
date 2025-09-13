import configparser
import time
import logging
from datetime import datetime, time as dt_time
import pandas as pd
from kiteconnect import KiteConnect, KiteException
import numpy as np

# --- Configuration ---
CONFIG_FILE = 'config.ini'
LOG_FILE = 'intraday_avwap_bot.log'

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
            except KiteException as e:
                logging.warning(f"Saved token invalid: {e}. Attempting full login.")

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
def get_stock_of_the_day(kite, stock_list):
    try:
        instruments = [f"NSE:{stock}" for stock in stock_list]
        quotes = kite.quote(instruments)

        if not quotes:
            logging.error("Could not fetch quotes for the stock list.")
            return None

        max_change = -100
        top_stock = None
        for stock in stock_list:
            instrument = f"NSE:{stock}"
            if instrument in quotes and quotes[instrument]['last_price'] > 0:
                ohlc = quotes[instrument]['ohlc']
                # Correctly calculate intraday change from the day's open price
                change = (quotes[instrument]['last_price'] / ohlc['open'] - 1) * 100
                if change > max_change:
                    max_change = change
                    top_stock = stock

        if top_stock:
            logging.info(f"Stock of the day: {top_stock} with {max_change:.2f}% change.")
            return top_stock
        else:
            logging.warning("Could not determine top stock of the day.")
            return None

    except Exception as e:
        logging.error(f"Error getting stock of the day: {e}")
        return None

def fetch_historical_data(kite, instrument_token, interval='5minute'):
    try:
        # By default, fetch data for the current trading day.
        # Kite API fetches data up to the current time.
        from_date = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        to_date = datetime.now()
        records = kite.historical_data(instrument_token, from_date, to_date, interval, continuous=False, oi=False)

        if not records:
            return None

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        logging.error(f"Failed to fetch historical data for token {instrument_token}: {e}")
        return None

def calculate_avwap_bands(df, std_dev_multiplier):
    df['TP'] = (df['high'] + df['low'] + df['close']) / 3
    df['TPV'] = df['TP'] * df['volume']
    df['cum_TPV'] = df['TPV'].cumsum()
    df['cum_volume'] = df['volume'].cumsum()
    df['avwap'] = df['cum_TPV'] / df['cum_volume']

    # Calculate Standard Deviation for bands
    df['sq_diff'] = ((df['close'] - df['avwap']) ** 2) * df['volume']
    df['cum_sq_diff'] = df['sq_diff'].cumsum()
    df['mean_sq_err'] = df['cum_sq_diff'] / df['cum_volume']
    df['std_dev'] = np.sqrt(df['mean_sq_err'])

    df['upper_band'] = df['avwap'] + (df['std_dev'] * std_dev_multiplier)
    df['lower_band'] = df['avwap'] - (df['std_dev'] * std_dev_multiplier)
    return df

def place_mis_order(kite, tradingsymbol, transaction_type, quantity):
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            quantity=quantity,
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET
        )
        logging.info(f"Placed MIS {transaction_type} order for {quantity} of {tradingsymbol}. Order ID: {order_id}")
        return order_id
    except Exception as e:
        logging.error(f"Failed to place MIS {transaction_type} order for {tradingsymbol}: {e}")
        return None

from datetime import datetime, time as dt_time, timedelta

def get_next_market_open_sleep_duration():
    now = datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)

    # If it's already past market open today, calculate for tomorrow
    if now > market_open:
        market_open += timedelta(days=1)

    # Handle weekends
    if market_open.weekday() == 5: # Saturday
        market_open += timedelta(days=2)
    elif market_open.weekday() == 6: # Sunday
        market_open += timedelta(days=1)

    sleep_duration = (market_open - now).total_seconds()
    return sleep_duration

# --- Main Bot Loop ---
def run_bot():
    config = load_config()
    kite = kite_login(config)

    if not kite:
        return

    bot_config = config['INTRADAY_AVWAP_BOT']
    stock_list = [s.strip() for s in bot_config['STOCKS_TO_MONITOR'].split(',')]
    capital_per_trade = float(bot_config['CAPITAL_PER_TRADE'])
    daily_stop_loss = float(bot_config['DAILY_STOP_LOSS'])
    std_dev_multiplier = float(bot_config['AVWAP_STDDEV_MULTIPLIER'])

    stock_of_the_day = None
    trading_halted = False

    while True:
        try:
            now = datetime.now()
            market_open_time = dt_time(9, 15)
            market_close_time = dt_time(15, 30)
            select_time = dt_time(9, 30)

            # --- Market Hours Logic ---
            if now.time() > market_close_time:
                logging.info("Market is closed for the day. Resetting for next day.")
                stock_of_the_day = None
                trading_halted = False
                sleep_duration = get_next_market_open_sleep_duration()
                logging.info(f"Sleeping for {sleep_duration/3600:.2f} hours until next market open.")
                time.sleep(sleep_duration)
                continue

            if now.time() < market_open_time:
                logging.info("Market is not open yet. Waiting...")
                time.sleep(60)
                continue

            if trading_halted:
                logging.warning("Daily stop loss hit. No new trades will be placed today.")
                time.sleep(300)
                continue

            # --- Select Stock of the Day at 9:30 AM ---
            if not stock_of_the_day and now.time() >= select_time:
                stock_of_the_day = get_stock_of_the_day(kite, stock_list)
                if not stock_of_the_day:
                    logging.error("Could not select a stock for today. Will retry tomorrow.")
                    trading_halted = True # Don't try again today
                    continue

            if not stock_of_the_day:
                logging.info("Waiting until 9:30 AM to select the stock of the day.")
                time.sleep(60)
                continue

            # --- Main Trading Logic (runs every 5 mins) ---
            positions = kite.positions()['net']
            open_position = next((p for p in positions if p['tradingsymbol'] == stock_of_the_day and p['product'] == 'MIS'), None)

            instrument_token = kite.ltp(f"NSE:{stock_of_the_day}")[f"NSE:{stock_of_the_day}"]["instrument_token"]
            df = fetch_historical_data(kite, instrument_token, interval='5minute')

            if df is None or df.empty:
                logging.warning(f"Could not fetch data for {stock_of_the_day}. Skipping this cycle.")
                time.sleep(300)
                continue

            df = calculate_avwap_bands(df, std_dev_multiplier)
            last_row = df.iloc[-1]
            ltp = last_row['close']

            # Check for exits first
            if open_position and open_position['quantity'] != 0:
                is_long = open_position['quantity'] > 0
                if is_long and ltp < last_row['lower_band']:
                    logging.info(f"Exit Long Signal for {stock_of_the_day}. Price crossed below lower band.")
                    place_mis_order(kite, stock_of_the_day, kite.TRANSACTION_TYPE_SELL, open_position['quantity'])
                elif not is_long and ltp > last_row['upper_band']:
                    logging.info(f"Exit Short Signal for {stock_of_the_day}. Price crossed above upper band.")
                    place_mis_order(kite, stock_of_the_day, kite.TRANSACTION_TYPE_BUY, abs(open_position['quantity']))

            # Check for entries if no position
            else:
                qty = int(capital_per_trade / ltp)
                if qty > 0:
                    if ltp > last_row['upper_band']:
                        logging.info(f"Long Entry Signal for {stock_of_the_day}. Price crossed above upper band.")
                        place_mis_order(kite, stock_of_the_day, kite.TRANSACTION_TYPE_BUY, qty)
                    elif ltp < last_row['lower_band']:
                        logging.info(f"Short Entry Signal for {stock_of_the_day}. Price crossed below lower band.")
                        place_mis_order(kite, stock_of_the_day, kite.TRANSACTION_TYPE_SELL, qty)

            # --- Daily Stop Loss Check ---
            pnl = kite.pnl()
            if pnl and 'realised' in pnl:
                daily_pnl = sum(p['pnl'] for p in pnl['realised'])
                if daily_pnl <= daily_stop_loss:
                    logging.critical(f"DAILY STOP LOSS HIT! Realized P&L: {daily_pnl:.2f}. Halting all new trades for the day.")
                    trading_halted = True


            time.sleep(300) # Sleep for 5 minutes

        except KiteException as e:
            logging.error(f"Kite API Error: {e}")
            if e.code == 403:
                logging.info("Token expired. Attempting to re-login.")
                kite = kite_login(config)
                if not kite:
                    logging.error("Re-login failed. Exiting.")
                    break
            time.sleep(60)
        except Exception as e:
            logging.error(f"An unexpected error occurred in the main loop: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_bot()
