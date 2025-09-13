# Advanced Intraday Trading Bot for Kite

This project contains a Python script for an automated intraday trading bot that connects to the Kite Connect API. It uses a dynamic, sentiment-based stock selection process and a breakout strategy based on Anchored VWAP.

## Strategy Overview

The bot's logic is executed in two main phases:

### 1. Stock Selection (at 9:30 AM)
At the start of the trading day, the bot determines the market sentiment and selects up to 2 stocks to trade from the Nifty 500 universe:
1.  **Universe:** The bot loads the list of Nifty 500 stocks from `nifty500.txt`.
2.  **Market Sentiment:** It fetches quotes for all 500 stocks and calculates an Advance/Decline ratio to gauge the market direction.
3.  **Liquidity Filter:** It filters out stocks that have not met a minimum traded value (`LIQUIDITY_THRESHOLD` in `config.ini`) to avoid trading illiquid instruments.
4.  **Selection Logic:**
    *   **If Advances > Declines (Bullish):** The bot selects the **top 2 gaining stocks** from the liquid Nifty 500 universe.
    *   **If Declines >= Advances (Bearish):** The bot selects the **top 2 losing stocks**.
5.  These 2 stocks become the candidates for trading for the rest of the day.

### 2. Trade Execution (5-minute Timeframe)
For each of the selected stocks, the bot applies the following Anchored VWAP (AVWAP) breakout strategy:
*   **Indicator:** It calculates an AVWAP anchored to the 9:15 AM open, along with upper and lower standard deviation bands.
*   **BUY (Long) Signal:** When the price breaks out and crosses **above the Upper AVWAP Band**.
*   **SELL (Short) Signal:** When the price breaks down and crosses **below the Lower AVWAP Band**.
*   **Exit Signal:** An open position (either long or short) is closed if the price crosses the opposite band.

### 3. Risk Management
*   **Capital per Trade:** The bot allocates a fixed amount of capital (e.g., ₹10,000) for each new trade.
*   **Daily Stop-Loss:** The bot will halt all new trading for the day if the total realized loss reaches a predefined limit (e.g., -₹3,000).

## How to Use

### 1. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Configure the Bot
1.  Open `config.ini` and fill in your Kite Connect API credentials under the `[KITE]` section.
2.  Customize the parameters in the `[INTRADAY_AVWAP_BOT]` section:
    *   `CAPITAL_PER_TRADE`: The amount of capital to allocate for each new trade.
    *   `DAILY_STOP_LOSS`: The maximum loss for the day (as a negative number) before the bot stops trading.
    *   `AVWAP_STDDEV_MULTIPLIER`: The multiplier for the standard deviation bands (e.g., 1.0, 2.0).
    *   `LIQUIDITY_THRESHOLD`: The minimum traded value (price * volume) a stock must have by 9:30 AM to be considered for trading.

### 3. Run the Bot
```bash
python3 intraday_avwap_bot.py
```

#### First-time Login
The first time you run the bot, it will need to generate a session. It will print a login URL.
1.  Copy the URL and open it in your browser.
2.  Log in with your Kite credentials.
3.  You will be redirected to your redirect URL. Copy the `request_token` from the URL query parameters (e.g., `.../?request_token=YOUR_TOKEN`).
4.  Paste this `request_token` into the terminal when prompted.

The bot will then save the generated `access_token` to `config.ini` and use it for future runs.

### 4. Running Continuously
This script is designed to run continuously. For real-world use, you should run it on a server or a reliable machine using a process manager like `supervisor` (on Linux) or `tmux` to ensure it keeps running even if you disconnect.

### Disclaimer
This script is for educational and demonstrational purposes only. Automated trading involves significant risk. **Always test thoroughly with a paper trading account before deploying with real money.**
