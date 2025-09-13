# Trading Strategy Backtester and Kite Trading Terminal

This project contains two main components:
1.  A backtesting script to test a trading strategy using historical data.
2.  A command-line interface (CLI) trading terminal for the Kite Connect API.

## 1. Backtesting

The `backtester.py` script is designed to backtest a trading strategy based on the following rules:
- **Strategy:** Buy a stock when its close price is 2% lower than its 50-period Exponential Moving Average (EMA).
- **Exit:** Sell the stock for a 2% profit.
- **Capital Allocation:** ₹50,000 per trade.
- **Universe:** Nifty 500 stocks (a list is provided in `nifty500.txt`).

### How to Run the Backtester

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Script:**
    ```bash
    python3 backtester.py
    ```

### How to Run the Backtester

1.  **Get API Credentials:**
    *   Go to the [ICICI Direct Breeze API page](https://www.icicidirect.com/futures-and-options/api/breeze) and register for an app to get your `api_key` and `secret_key`.

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Script:**
    ```bash
    python3 backtester.py
    ```

4.  **Login to ICICI Direct (Breeze):**
    *   When you run the script, it will prompt you for your `api_key` and `secret_key`.
    *   It will then display a login URL. Copy this URL and open it in your browser.
    *   Log in with your ICICI Direct credentials.
    *   After logging in, you will be redirected to a new URL. Copy the `api_session` (session token) from this URL.
    *   Paste the `api_session` back into the terminal when prompted.

### **NOTE**
The backtester is configured to fetch 1 year of **daily** data for the first 5 stocks in `nifty500.txt`. The 1-hour interval was not directly available in the historical API, so daily data is used. You can modify these settings in the `run_backtest` function in `backtester.py`.

## 2. Kite Trading Terminal

The `trading_terminal.py` script is a simple CLI application that allows you to interact with the Kite Connect API.

### Features
- Login to your Kite Connect account.
- Place buy and sell orders.
- View your current positions.
- View your order book.

### How to Use the Trading Terminal

1.  **Get API Credentials:**
    - Go to the [Kite Connect Developer portal](https://developers.kite.trade/).
    - Create an app to get your `api_key` and `api_secret`.
    - Set your `redirect_url` to something like `https://127.0.0.1`.

2.  **Run the Script:**
    ```bash
    python3 trading_terminal.py
    ```

3.  **Login Flow:**
    - When you run the script, select option `1. Login`.
    - Enter your `api_key` and `api_secret`.
    - The script will generate a login URL. Copy this URL and paste it into your web browser.
    - Log in with your Kite credentials.
    - After successful login, you will be redirected to your `redirect_url`. The URL will contain a `request_token` (e.g., `https://127.0.0.1/?request_token=YOUR_REQUEST_TOKEN`).
    - Copy the `request_token` and paste it back into the terminal when prompted.
    - If the login is successful, you can start using the other features of the terminal.

### **NOTE**
This is a basic implementation and does not include advanced features like error handling for all possible API responses, storing session tokens, or handling WebSocket connections for live data. It is intended as a starting point for building a more robust trading application.

---

## 3. ETF/MTF Algo Trading Bot

The `etf_mtf_bot.py` script is a trading bot that automatically executes a strategy on ETFs using the Kite Connect API.

### Strategy
- **Universe:** All available ETFs on NSE.
- **Timeframe:** 1 hour.
- **Entry:** Place an MTF buy order when an ETF's close price is 2% below its 50-period EMA.
- **Exit:** Sell the ETF when it reaches a 2% profit target.
- **Capital:** Deploys a total capital of ₹100,000.

### How to Use the Trading Bot

1.  **Install TA-Lib (if needed):**
    The bot uses the `TA-Lib` library for technical analysis. Installing this can be complex. If `pip install -r requirements.txt` fails at the `TA-Lib` step, you will need to install the TA-Lib C library on your system first.
    - **For Ubuntu/Debian:** `sudo apt-get install libta-lib-dev`
    - **For macOS:** `brew install ta-lib`
    - **For Windows:** Download the `ta-lib-0.4.0-msvc.zip` file and follow instructions online.

2.  **Install Dependencies:**
    Once the TA-Lib library is set up, install the Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the Bot:**
    - Open the `config.ini` file.
    - Enter your Kite `API_KEY` and `API_SECRET` in the `[KITE]` section.
    - You can adjust the trading parameters in the `[TRADING]` section if needed.

4.  **Run the Bot:**
    ```bash
    python3 etf_mtf_bot.py
    ```

5.  **First-time Login:**
    - The first time you run the bot, it will fail to log in with an access token and will prompt you to perform a manual login.
    - Follow the same login flow as the trading terminal: open the URL, log in, and paste the `request_token` from the redirect URL back into the terminal.
    - The bot will save your `access_token` to `config.ini` and will use it for subsequent runs, attempting to log in automatically.

6.  **Running Continuously:**
    This script is designed to run continuously. For real-world use, you should run it on a server using a process manager like `supervisor` or `systemd`, or in a `screen` or `tmux` session to ensure it keeps running even if you disconnect.
