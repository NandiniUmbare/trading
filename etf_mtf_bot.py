import configparser
import time
import logging
from datetime import datetime, time as dt_time
import pandas as pd
import talib
from kiteconnect import KiteConnect, KiteException

# --- Configuration ---
CONFIG_FILE = 'config.ini'
LOG_FILE = 'etf_mtf_bot.log'

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
                # Check if the token is still valid by making a simple call
                kite.profile()
                logging.info("Logged in successfully using saved access token.")
                return kite
            except KiteException as e:
                logging.warning(f"Failed to login with saved token: {e}. Attempting full login.")

        # If no access token or it's invalid, proceed with full login
        print("Please open the following URL in your browser to login:")
        print(kite.login_url())
        request_token = input("Enter the request_token from the redirect URL: ")

        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)

        save_access_token(config, access_token)
        logging.info("Login successful. New access token has been saved.")
        return kite

    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        return None

# --- Core Trading Logic ---
def get_etf_list(kite):
    try:
        instruments = kite.instruments("NSE")
        etfs = [ins for ins in instruments if ins['instrument_type'] == 'ETF' and ins['exchange'] == 'NSE']
        logging.info(f"Found {len(etfs)} ETFs on NSE.")
        return etfs
    except Exception as e:
        logging.error(f"Failed to get ETF list: {e}")
        return []

def fetch_historical_data(kite, instrument_token, interval='60minute'):
    try:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=15) # Fetch enough data for EMA calculation
        records = kite.historical_data(instrument_token, from_date, to_date, interval, continuous=False, oi=False)

        if not records:
            return None

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        logging.error(f"Failed to fetch historical data for token {instrument_token}: {e}")
        return None

def place_mtf_buy_order(kite, tradingsymbol, capital_per_trade):
    try:
        ltp_data = kite.ltp(f"NSE:{tradingsymbol}")
        ltp = ltp_data[f"NSE:{tradingsymbol}"]["last_price"]
        quantity = int(capital_per_trade / ltp)

        if quantity == 0:
            logging.warning(f"Could not afford any shares of {tradingsymbol} with capital {capital_per_trade}.")
            return None

        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=tradingsymbol,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=quantity,
            product=kite.PRODUCT_CNC, # Using CNC for MTF
            order_type=kite.ORDER_TYPE_MARKET
        )
        logging.info(f"Placed MTF BUY order for {quantity} of {tradingsymbol}. Order ID: {order_id}")
        return order_id
    except Exception as e:
        logging.error(f"Failed to place MTF buy order for {tradingsymbol}: {e}")
        return None

def place_sell_order(kite, tradingsymbol, quantity):
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=tradingsymbol,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=quantity,
            product=kite.PRODUCT_CNC,
            order_type=kite.ORDER_TYPE_MARKET
        )
        logging.info(f"Placed SELL order for {quantity} of {tradingsymbol}. Order ID: {order_id}")
        return order_id
    except Exception as e:
        logging.error(f"Failed to place sell order for {tradingsymbol}: {e}")
        return None

# --- Main Bot Loop ---
def run_bot():
    config = load_config()
    kite = kite_login(config)

    if not kite:
        logging.error("Could not log in to Kite. Exiting.")
        return

    trading_config = config['TRADING']
    total_capital = float(trading_config['TOTAL_CAPITAL'])
    profit_target = float(trading_config['PROFIT_TARGET_PERCENT'])
    ema_period = int(trading_config['EMA_PERIOD'])
    entry_percent = float(trading_config['ENTRY_PERCENT_BELOW_EMA'])

    etf_list = get_etf_list(kite)
    if not etf_list:
        logging.error("Could not fetch ETF list. Exiting.")
        return

    while True:
        try:
            # --- Market Hours Check ---
            market_open = dt_time(9, 15)
            market_close = dt_time(15, 30)
            now = datetime.now().time()
            if not (market_open <= now <= market_close):
                logging.info("Market is closed. Sleeping until it opens.")
                time.sleep(60)
                continue

            logging.info("--- Starting new cycle ---")

            # --- Get current positions and capital usage ---
            positions = kite.positions()['net']
            open_positions = {pos['tradingsymbol']: pos for pos in positions if pos['quantity'] != 0}
            capital_used = sum(pos['quantity'] * pos['average_price'] for pos in open_positions.values())

            logging.info(f"Open positions: {list(open_positions.keys())}")
            logging.info(f"Capital used: {capital_used:.2f} / {total_capital:.2f}")

            # --- Check for exits ---
            for symbol, pos_data in open_positions.items():
                ltp_data = kite.ltp(f"NSE:{symbol}")
                ltp = ltp_data[f"NSE:{symbol}"]["last_price"]
                pnl_percent = (ltp - pos_data['average_price']) / pos_data['average_price']

                if pnl_percent >= profit_target:
                    logging.info(f"Profit target hit for {symbol}. P&L: {pnl_percent*100:.2f}%. Selling.")
                    place_sell_order(kite, symbol, pos_data['quantity'])

            # --- Check for entries ---
            capital_available = total_capital - capital_used
            if capital_available > 1000: # Minimum amount to consider a trade
                capital_per_trade = capital_available # Use all available capital for the next trade

                for etf in etf_list:
                    symbol = etf['tradingsymbol']
                    if symbol not in open_positions:
                        df = fetch_historical_data(kite, etf['instrument_token'])
                        if df is not None and len(df) > ema_period:
                            df['ema'] = talib.EMA(df['close'], timeperiod=ema_period)
                            last_close = df['close'].iloc[-1]
                            last_ema = df['ema'].iloc[-1]

                            if last_close < last_ema * (1 - entry_percent):
                                logging.info(f"Entry signal for {symbol}. Close: {last_close}, EMA: {last_ema:.2f}. Placing buy order.")
                                place_mtf_buy_order(kite, symbol, capital_per_trade)
                                # Break after placing one order to re-evaluate capital in the next cycle
                                break

            logging.info("--- Cycle finished. Sleeping for 1 hour. ---")
            time.sleep(3600)

        except KiteException as e:
            logging.error(f"Kite API Error: {e}")
            if e.code == 403: # Token exception
                logging.info("Token expired. Attempting to re-login.")
                kite = kite_login(config)
                if not kite:
                    logging.error("Re-login failed. Exiting.")
                    break
            time.sleep(60)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_bot()
