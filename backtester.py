import backtrader as bt
import pandas as pd
import random
from datetime import datetime, timedelta
from pya3 import *

# Global Alice Blue client
alice = None

# --- Alice Blue Login ---
def alice_blue_login():
    """
    Handles the login process for Alice Blue.
    """
    global alice
    print("--- Login to Alice Blue ---")

    # It's recommended to store these securely, e.g., in environment variables or a config file
    try:
        user_id = input("Enter your Alice Blue User ID: ")
        api_key = input("Enter your Alice Blue API Key: ")

        alice = Aliceblue(user_id=user_id, api_key=api_key)
        session_id = alice.get_session_id()

        if session_id['status'] == 'Success':
            print("\nAlice Blue Login Successful!")
            print(f"Session ID: {session_id['sessionID']}")
        else:
            print(f"\nLogin failed: {session_id.get('emsg', 'Unknown error')}")
            alice = None

    except Exception as e:
        print(f"\nAn error occurred during login: {e}")
        alice = None

    return alice


# --- Trading Strategy ---
class EmaStrategy(bt.Strategy):
    """
    Buy when the close price is 2% lower than the 50-period EMA.
    Sell when the price reaches a 2% profit target.
    """
    params = (
        ('ema_period', 50),
        ('price_diff_percent', 0.02),
        ('target_profit_percent', 0.02),
    )

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Add a 50-period EMA indicator
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.p.ema_period
        )

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                )
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log(f'Close, {self.dataclose[0]:.2f}')

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # Not yet in the market, we might buy
            if self.dataclose[0] < self.ema[0] * (1 - self.p.price_diff_percent):
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy()
        else:
            # Already in the market, we might sell
            if self.dataclose[0] >= self.buyprice * (1 + self.p.target_profit_percent):
                self.log(f'SELL CREATE, {self.dataclose[0]:.2f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()


# --- Data Fetching from Alice Blue ---
def get_historical_data(alice, symbol, from_date, to_date, interval='60', exchange='NSE'):
    """
    Fetches historical data from Alice Blue.
    """
    print(f"--- Fetching data for {symbol} ---")
    try:
        instrument = alice.get_instrument_by_symbol(exchange, symbol)
        if not instrument:
            print(f"Could not find instrument for {symbol}")
            return None

        candles = alice.get_historical(instrument, from_date, to_date, interval, indices=False)

        if not candles:
            print(f"No data received for {symbol}")
            return None

        # Convert to pandas DataFrame
        df = pd.DataFrame(candles)

        # The pya3 documentation is not explicit on the column names,
        # but based on common formats, we assume the following.
        # You may need to adjust this based on the actual output.
        df['datetime'] = pd.to_datetime(df['time'])
        df.set_index('datetime', inplace=True)
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }, inplace=True)

        # Ensure required columns are present
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"Historical data for {symbol} is missing one of the required columns: {required_cols}")
            return None

        return df[['open', 'high', 'low', 'close', 'volume']]

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None


# --- Sizer for Fixed Cash Allocation ---
class FixedCashAmount(bt.Sizer):
    params = (('amount', 50000),)

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            size = self.p.amount / data.close[0]
            return size
        return self.broker.getposition(data).size

# --- Main Execution ---
def run_backtest():
    # --- Login to Alice Blue ---
    global alice
    if not alice_blue_login():
        return

    # --- Backtest Setup ---
    cerebro = bt.Cerebro()
    cerebro.addstrategy(EmaStrategy)

    try:
        with open('nifty500.txt', 'r') as f:
            symbols = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: nifty500.txt not found. Please create this file.")
        return

    # Download master contract
    print("Downloading master contract for NSE...")
    alice.get_contract_master('NSE')
    print("Master contract downloaded.")

    symbols_to_run = symbols[:5]  # Running on first 5 symbols for demonstration
    print(f"Running backtest for: {', '.join(symbols_to_run)}")

    # Define the date range for historical data
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365) # 1 year of data

    for symbol in symbols_to_run:
        dataframe = get_historical_data(alice, symbol, from_date, to_date, interval='60')
        if dataframe is not None and not dataframe.empty:
            data = bt.feeds.PandasData(dataname=dataframe, name=symbol)
            cerebro.adddata(data, name=symbol)

    cerebro.broker.setcash(200000.0) # Initial capital
    cerebro.addsizer(FixedCashAmount, amount=50000)
    cerebro.broker.setcommission(commission=0.002) # 0.2% commission on trades

    print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')

    results = cerebro.run()

    print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # Print analysis
    print("\n--- Backtest Analysis ---")
    strat = results[0]
    analyzers = strat.analyzers

    sharpe_ratio = analyzers.sharpe_ratio.get_analysis()
    drawdown = analyzers.drawdown.get_analysis()
    returns = analyzers.returns.get_analysis()
    trade_analyzer = analyzers.trade_analyzer.get_analysis()

    print(f"Sharpe Ratio: {sharpe_ratio.get('sharperatio', 'N/A')}")
    print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")
    print(f"Annualized Return: {returns.get('rnorm100', 'N/A'):.2f}%")

    if trade_analyzer.total.total > 0:
        print(f"Total Trades: {trade_analyzer.total.total}")
        print(f"Winning Trades: {trade_analyzer.won.total}")
        print(f"Losing Trades: {trade_analyzer.lost.total}")
        print(f"Win Rate: {(trade_analyzer.won.total / trade_analyzer.total.total) * 100:.2f}%")
    else:
        print("No trades were executed.")

    # cerebro.plot() # Uncomment to plot the results if you have a graphical backend

if __name__ == '__main__':
    print("--- Starting Backtest ---")
    print("NOTE: This script uses dummy data for demonstration.")
    print("You need to replace the `get_historical_data` function with your actual data fetching logic using the Alice Blue API.")
    run_backtest()
    print("--- Backtest Finished ---")
