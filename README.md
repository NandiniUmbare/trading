# Advanced Intraday Trading Bot for Kite

This project contains a Python script for an automated intraday trading bot that connects to the Kite Connect API. It uses a dynamic stock selection strategy based on market sentiment and a breakout strategy based on Anchored VWAP.

## Strategy Overview

The bot's logic is executed in two main phases:

### 1. Stock Selection (at 9:30 AM)
At the start of the trading day, the bot determines the market sentiment and selects up to 3 stocks to trade:
1.  **Market Sentiment:** It checks the Advance/Decline ratio of the stocks in your watchlist. (Note: This is a simplified proxy for market sentiment, as a live, full-market A/D ratio is not available via the API).
2.  **Bullish Scenario (Advances > Declines):** The bot identifies the **top 3 performing stocks** from your watchlist based on the highest positive percentage change since the 9:15 AM open.
3.  **Bearish Scenario (Declines >= Advances):** The bot identifies the **top 3 losing stocks** from your watchlist based on the highest negative percentage change.
4.  These 3 stocks become the candidates for trading for the rest of the day.

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

### 1. Install Python Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Configure the Bot
1.  Open `config.ini` and fill in your Kite Connect API credentials under the `[KITE]` section.
2.  Customize the parameters in the `[INTRADAY_AVWAP_BOT]` section:
    *   `STOCKS_TO_MONITOR`: A comma-separated list of stock symbols to monitor for the selection process.
    *   `CAPITAL_PER_TRADE`: The amount of capital to allocate for each new trade.
    *   `DAILY_STOP_LOSS`: The maximum loss for the day (as a negative number) before the bot stops trading.
    *   `AVWAP_STDDEV_MULTIPLIER`: The multiplier for the standard deviation bands (e.g., 1.0, 2.0).

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

The bot will then save the generated `access_token` to `config.ini` and use it for future runs, minimizing the need for manual logins.

### 4. Running Continuously
This script is designed to run continuously throughout the trading day. For real-world use, you should run it on a server or a reliable machine using a process manager like `supervisor` (on Linux) or `tmux` to ensure it keeps running even if you disconnect.

### Disclaimer
This script is for educational and demonstrational purposes only. Automated trading involves significant risk, including the risk of losing your entire investment. The author is not responsible for any financial losses incurred by using this script. **Always test thoroughly with a paper trading account before deploying with real money.**
