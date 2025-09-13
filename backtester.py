import backtrader as bt
import pandas as pd
import random
from datetime import datetime, timedelta
from breeze_connect import BreezeConnect
import urllib

# Global Breeze client
breeze = None

# --- ICICI Direct (Breeze) Login ---
def icici_direct_login():
    """
    Handles the login process for ICICI Direct's Breeze API.
    """
    global breeze
    print("--- Login to ICICI Direct (Breeze API) ---")

    try:
        api_key = input("Enter your Breeze API Key: ")
        secret_key = input("Enter your Breeze Secret Key: ")

        breeze = BreezeConnect(api_key=api_key)

        # Generate login URL and print it for the user
        login_url = f"https://api.icicidirect.com/apiuser/login?api_key={urllib.parse.quote_plus(api_key)}"
        print("\nPlease open the following URL in your browser to login:")
        print(login_url)

        # The user will be redirected with a session_token.
        session_token = input("\nEnter the api_session (session_token) from the redirect URL: ")

        # Generate session
        breeze.generate_session(api_secret=secret_key, session_token=session_token)

        print("\nICICI Direct Login Successful!")
        # You can now make other API calls, e.g., get customer details
        # print(breeze.get_customer_details(api_session=session_token))

    except Exception as e:
        print(f"\nLogin failed: {e}")
        breeze = None

    return breeze


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


# --- Data Fetching from ICICI Direct (Breeze) ---
def get_historical_data(breeze, symbol, from_date, to_date, interval='1day', exchange='NSE'):
    """
    Fetches historical data from ICICI Direct's Breeze API.
    """
    print(f"--- Fetching data for {symbol} ---")
    try:
        # Convert datetimes to the required ISO format string
        from_iso = from_date.isoformat()[:19] + '.000Z'
        to_iso = to_date.isoformat()[:19] + '.000Z'

        candles = breeze.get_historical_data_v2(
            interval=interval,
            from_date=from_iso,
            to_date=to_iso,
            stock_code=symbol,
            exchange_code=exchange,
            product_type="cash"
        )

        if not candles or candles.get('Success') is None:
            print(f"No data received for {symbol} or request failed.")
            if candles.get('Error'):
                print(f"API Error: {candles.get('Error')}")
            return None

        # Convert to pandas DataFrame
        df = pd.DataFrame(candles['Success'])

        if df.empty:
            print(f"No historical data returned for {symbol}")
            return None

        # The breeze documentation shows the datetime key is 'datetime'
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)

        # Ensure data types are correct for backtrader
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])

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
    # --- Login to ICICI Direct (Breeze) ---
    global breeze
    if not icici_direct_login():
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

    symbols_to_run = symbols[:5]  # Running on first 5 symbols for demonstration
    print(f"Running backtest for: {', '.join(symbols_to_run)}")

    # Define the date range for historical data
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365) # 1 year of data

    for symbol in symbols_to_run:
        dataframe = get_historical_data(breeze, symbol, from_date, to_date, interval='1day')
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
