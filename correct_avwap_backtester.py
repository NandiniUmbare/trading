import configparser
import time
import logging
from datetime import datetime, timedelta, date, time as dt_time
import pandas as pd
from kiteconnect import KiteConnect, KiteException
import numpy as np
import backtrader as bt

# --- Configuration ---
CONFIG_FILE = 'config.ini'
LOG_FILE = 'correct_avwap_backtester.log'

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

# --- Custom Backtrader Indicator for Anchored VWAP ---
class AnchoredVWAP(bt.Indicator):
    lines = ('avwap', 'upper_band', 'lower_band',)
    params = (('std_dev_multiplier', 1.0),)

    def __init__(self):
        self.cum_tpv = 0.0
        self.cum_volume = 0.0
        self.cum_sq_diff = 0.0

    def next(self):
        tp = (self.data.high[0] + self.data.low[0] + self.data.close[0]) / 3
        tpv = tp * self.data.volume[0]

        self.cum_tpv += tpv
        self.cum_volume += self.data.volume[0]

        if self.cum_volume > 0:
            self.lines.avwap[0] = self.cum_tpv / self.cum_volume
        else:
            self.lines.avwap[0] = self.data.close[0]

        sq_diff = ((self.data.close[0] - self.lines.avwap[0]) ** 2)
        self.cum_sq_diff += sq_diff

        num_bars = self.len()
        if num_bars > 0:
            mean_sq_err = self.cum_sq_diff / num_bars
            std_dev = np.sqrt(mean_sq_err)
            self.lines.upper_band[0] = self.lines.avwap[0] + (std_dev * self.p.std_dev_multiplier)
            self.lines.lower_band[0] = self.lines.avwap[0] - (std_dev * self.p.std_dev_multiplier)
        else:
            self.lines.upper_band[0] = self.lines.avwap[0]
            self.lines.lower_band[0] = self.lines.avwap[0]

# --- Backtesting Strategy ---
class AVWAPBreakoutStrategy(bt.Strategy):
    params = (('capital_per_trade', 10000),)

    def __init__(self):
        self.avwap = AnchoredVWAP(self.data)
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        # logging.info(f'{dt.isoformat()} - {txt}') # This can be too verbose

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            self.order = None

    def next(self):
        if self.order:
            return

        ltp = self.data.close[0]

        if self.position:
            if self.position.size > 0 and ltp < self.avwap.lower_band[0]:
                self.order = self.close()
            elif self.position.size < 0 and ltp > self.avwap.upper_band[0]:
                self.order = self.close()
        else:
            qty = int(self.p.capital_per_trade / ltp)
            if qty > 0:
                if ltp > self.avwap.upper_band[0]:
                    self.order = self.buy(size=qty)
                elif ltp < self.avwap.lower_band[0]:
                    self.order = self.sell(size=qty)

# --- Main Backtesting Function ---
def run_backtest():
    config = load_config()
    kite = kite_login(config)
    if not kite:
        return

    bot_config = config['INTRADAY_AVWAP_BOT']
    stock_list = [s.strip() for s in bot_config['STOCKS_TO_MONITOR'].split(',')]
    daily_stop_loss = float(bot_config['DAILY_STOP_LOSS'])

    # 1. Pre-fetch all data
    logging.info("Starting massive data download for all stocks for the last year. This will take a long time...")
    all_data = {}
    instrument_map = {inst['tradingsymbol']: inst['instrument_token'] for inst in kite.instruments('NSE')}

    to_date = date.today()
    from_date = to_date - timedelta(days=365)

    for stock in stock_list:
        try:
            if stock in instrument_map:
                token = instrument_map[stock]
                records = kite.historical_data(token, from_date, to_date, "5minute")
                if records:
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    all_data[stock] = df
                    logging.info(f"Successfully fetched data for {stock}")
            else:
                logging.warning(f"Could not find instrument token for {stock}")
            time.sleep(0.5) # Rate limiting
        except Exception as e:
            logging.error(f"Could not fetch data for {stock}: {e}")

    logging.info("Data download complete.")

    # 2. Loop through each day and backtest
    total_pnl = 0.0
    total_trades = 0
    winning_trades = 0

    trading_days = pd.to_datetime(list(set(d.date() for df in all_data.values() for d in df['date']))).sort_values()

    for day in trading_days:
        if day.weekday() >= 5: continue

        logging.info(f"--- Backtesting for date: {day.strftime('%Y-%m-%d')} ---")

        # Determine stock of the day
        top_stock = None
        max_change = -100

        open_time = datetime.combine(day, dt_time(9, 15))
        select_time = datetime.combine(day, dt_time(9, 30))

        for stock, df in all_data.items():
            day_df = df[df['date'].dt.date == day.date()]
            if not day_df.empty:
                try:
                    open_price = day_df[day_df['date'] >= open_time].iloc[0]['open']
                    select_price = day_df[day_df['date'] >= select_time].iloc[0]['close']
                    change = (select_price / open_price - 1) * 100
                    if change > max_change:
                        max_change = change
                        top_stock = stock
                except IndexError:
                    continue # Not enough data for this stock on this day

        if not top_stock:
            logging.warning(f"Could not determine top stock for {day.date()}. Skipping.")
            continue

        logging.info(f"Stock of the day: {top_stock} with {max_change:.2f}% change.")

        # Run backtest for this day and this stock
        try:
            cerebro = bt.Cerebro()
            day_data = all_data[top_stock][all_data[top_stock]['date'].dt.date == day.date()]
            data_feed = bt.feeds.PandasData(dataname=day_data.set_index('date'))

            cerebro.adddata(data_feed)
            cerebro.addstrategy(AVWAPBreakoutStrategy, daily_stop_loss=daily_stop_loss)
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
            cerebro.broker.set_cash(100000)
            cerebro.broker.setcommission(commission=0.0005)

            results = cerebro.run()

            day_pnl = cerebro.broker.getvalue() - 100000
            total_pnl += day_pnl

            trade_analysis = results[0].analyzers.trade_analyzer.get_analysis()
            if trade_analysis and trade_analysis.total.total > 0:
                total_trades += trade_analysis.total.total
                winning_trades += trade_analysis.won.total

            logging.info(f"Day P&L: {day_pnl:.2f}")

        except Exception as e:
            logging.error(f"Failed backtest for {day.date()} on {top_stock}: {e}")

    # 3. Final Report
    logging.info("--- Backtest Finished ---")
    logging.info(f"Total P&L over the last year: {total_pnl:.2f}")
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100
        logging.info(f"Total Trades: {total_trades}")
        logging.info(f"Winning Trades: {winning_trades}")
        logging.info(f"Win Rate: {win_rate:.2f}%")
    else:
        logging.info("No trades were executed during the backtest period.")

if __name__ == '__main__':
    run_backtest()
