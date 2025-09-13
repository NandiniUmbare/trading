# Intraday AVWAP Breakout Trading Bot for Kite

This project contains a Python script for an automated intraday trading bot that connects to the Kite Connect API.

## Strategy Overview

The bot employs a momentum-based breakout strategy using an Anchored VWAP (AVWAP).

1.  **Stock Selection (at 9:30 AM):** At the start of the trading day, the bot identifies the top-performing stock from a predefined list of highly liquid stocks (configurable in `config.ini`).
2.  **Indicator:** For the selected stock, it calculates an Anchored VWAP (AVWAP) starting from the 9:15 AM open, along with upper and lower standard deviation bands.
3.  **Trading Signals (5-minute timeframe):**
    *   **BUY (Long):** When the price breaks out and crosses **above the Upper AVWAP Band**.
    *   **SELL (Short):** When the price breaks down and crosses **below the Lower AVWAP Band**.
    *   **EXIT:** An open position (either long or short) is closed if the price crosses the opposite band.
4.  **Risk Management:**
    *   **Capital per Trade:** The bot allocates a fixed amount of capital (e.g., ₹10,000) for each trade.
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
    *   `STOCKS_TO_MONITOR`: A comma-separated list of stock symbols to monitor.
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

### 5. Running Continuously
This script is designed to run continuously throughout the trading day. For real-world use, you should run it on a server or a reliable machine using a process manager like `supervisor` (on Linux) or `tmux` to ensure it keeps running even if you disconnect.

### Disclaimer
This script is for educational and demonstrational purposes only. Automated trading involves significant risk, including the risk of losing your entire investment. The author is not responsible for any financial losses incurred by using this script. **Always test thoroughly with a paper trading account before deploying with real money.**
