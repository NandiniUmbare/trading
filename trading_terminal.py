import logging
from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variable to hold the KiteConnect instance
kite = None

def login():
    """
    Handles the login process for Kite Connect.
    """
    global kite
    print("--- Login to Kite Connect ---")

    # These should be stored securely, not hardcoded.
    # For this example, we'll take them as input.
    api_key = input("Enter your API Key: ")
    api_secret = input("Enter your API Secret: ")

    try:
        kite = KiteConnect(api_key=api_key)

        # Generate login URL
        print("\nPlease open the following URL in your browser to login:")
        print(kite.login_url())

        # The user will be redirected with a request_token.
        request_token = input("\nEnter the request_token from the redirect URL: ")

        # Generate session
        data = kite.generate_session(request_token, api_secret=api_secret)
        kite.set_access_token(data["access_token"])

        print("\nLogin Successful!")
        # It's better to use a non-sensitive identifier like nickname or user_id if available
        # For this example, we'll just show a success message.
        # print(f"Welcome, {data.get('user_name', 'user')}!")
        print("Welcome!")


    except Exception as e:
        print(f"\nLogin failed: {e}")
        kite = None

def place_order_cli():
    """
    CLI to place a buy or sell order.
    """
    if not kite:
        print("Please login first.")
        return

    print("--- Place Order ---")
    try:
        tradingsymbol = input("Enter Tradingsymbol (e.g., INFY): ").upper()
        exchange = input(f"Enter Exchange ({kite.EXCHANGE_NSE}, {kite.EXCHANGE_BSE}, etc.): ").upper()
        transaction_type = input(f"Enter Transaction Type ({kite.TRANSACTION_TYPE_BUY} or {kite.TRANSACTION_TYPE_SELL}): ").upper()
        quantity = int(input("Enter Quantity: "))
        order_type = input(f"Enter Order Type ({kite.ORDER_TYPE_MARKET} or {kite.ORDER_TYPE_LIMIT}): ").upper()

        price = None
        if order_type == kite.ORDER_TYPE_LIMIT:
            price = float(input("Enter Price: "))

        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            product=kite.PRODUCT_CNC,  # Using CNC for simplicity
            order_type=order_type,
            price=price,
            validity=kite.VALIDITY_DAY
        )
        print(f"\nOrder placed successfully. Order ID: {order_id}")

    except Exception as e:
        print(f"\nFailed to place order: {e}")


def view_positions_cli():
    """
    CLI to view current positions.
    """
    if not kite:
        print("Please login first.")
        return

    print("--- Current Positions ---")
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])

        if not net_positions:
            print("No open positions.")
            return

        print(f"{'Symbol':<15} {'Qty':<10} {'Avg Price':<15} {'LTP':<15} {'P&L':<15}")
        print("-" * 70)
        for pos in net_positions:
            # Ensure all keys exist before calculating P&L
            if 'last_price' in pos and 'average_price' in pos and 'quantity' in pos:
                pnl = (pos['last_price'] - pos['average_price']) * pos['quantity']
                print(f"{pos.get('tradingsymbol', ''):<15} {pos.get('quantity', 0):<10} {pos.get('average_price', 0):<15.2f} {pos.get('last_price', 0):<15.2f} {pnl:<15.2f}")
            else:
                print(f"{pos.get('tradingsymbol', ''):<15} - Data Incomplete")

    except Exception as e:
        print(f"\nFailed to fetch positions: {e}")

def view_orders_cli():
    """
    CLI to view the order book.
    """
    if not kite:
        print("Please login first.")
        return

    print("--- Order Book ---")
    try:
        orders = kite.orders()

        if not orders:
            print("No orders in the book.")
            return

        print(f"{'Order ID':<20} {'Symbol':<15} {'Type':<10} {'Qty':<10} {'Status':<15}")
        print("-" * 75)
        for order in orders:
            print(f"{order.get('order_id', ''):<20} {order.get('tradingsymbol', ''):<15} {order.get('transaction_type', ''):<10} {order.get('quantity', 0):<10} {order.get('status', ''):<15}")

    except Exception as e:
        print(f"\nFailed to fetch orders: {e}")


def main():
    """
    Main function to run the trading terminal.
    """
    while True:
        print("\n--- Kite Trading Terminal ---")
        print("1. Login")
        print("2. Place Order")
        print("3. View Positions")
        print("4. View Order Book")
        print("5. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            login()
        elif choice == '2':
            place_order_cli()
        elif choice == '3':
            view_positions_cli()
        elif choice == '4':
            view_orders_cli()
        elif choice == '5':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    print("--- Welcome to the Simple Kite Trading Terminal ---")
    print("NOTE: This is a basic implementation for demonstration purposes.")
    print("You will need a valid Kite Connect API key and secret to use it.")
    main()
