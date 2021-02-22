import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index(): # TODO: Let user be able to buy/sell stocks they own from index
    """Show portfolio of stocks"""
    # Get table of stocks owned
    stocks_table = db.execute("SELECT symbol, company_name, shares_owned FROM stocks_owned JOIN users ON user_id = users.id WHERE user_id = :userid",
                              userid=session["user_id"])

    # Clean up the table
    modified_table = modify_table(stocks_table)

     # Get the user's current balance
    cash_table = db.execute("SELECT cash FROM users WHERE id=:userid", userid=session["user_id"])
    user_cash = cash_table[0]["cash"]

    # Get the total money the user has
    user_total = get_user_total(modified_table, user_cash)

    return render_template("index.html", shares_table=modified_table, user_cash=user_cash, user_total=float(user_total))

# Modify the stocks table to prepare for displaying
def modify_table(stocks_table):
    modified_table = []

    for row in stocks_table:
        stock_info = {}

        stock_info["symbol"] = row["symbol"].upper()
        stock_info["name"] = row["company_name"]
        stock_info["shares"] = row["shares_owned"]

        # Get the current price of the stock
        response = lookup(row["symbol"])
        stock_info["stock_price"] = response["price"]

        stock_info["total"] = row["shares_owned"] * response["price"]

        modified_table.append(stock_info)

    return modified_table

# Add up the total amount of money the user has
def get_user_total(modified_table, user_cash):
    user_total = 0

    user_total += user_cash

    for row in modified_table:
        user_total += row["total"]

    return user_total

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy(): # TODO: Modify function to check if user already owns those stocks
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Check if symbol was entered
        if not symbol:
            return apology("must provide symbol", 403)

        # Check if no. of shares was entered
        if not shares:
            return apology("must provide number of shares", 403)

        # Retrieve price of a single stock price
        response = lookup(symbol)

        # If symbol does not exist
        if not response:
            return apology("symbol does not exist", 403)

        stock_price = response["price"]

        # Get the current amount of cash user has
        cash_table = db.execute("SELECT cash FROM users WHERE id=:userid", userid=session["user_id"])
        user_cash = cash_table[0]["cash"]

        # Calculate leftover cash after purchasing shares
        remaining_cash = user_cash - (stock_price * int(shares))
        if remaining_cash < 0:
            return apology("sorry ya broke", 403)

        # Insert new values into database
        new_pk_stocks = db.execute("INSERT INTO stocks_owned VALUES (:userid, :symbol, :company_name, :shares_owned)", userid=session["user_id"],
                                    symbol=symbol.upper(), company_name=response["name"], shares_owned=shares)

        if new_pk_stocks < 1:
            return apology("why", 403)

        rows_updated = db.execute("UPDATE users SET cash=:new WHERE id=:userid", new=remaining_cash, userid=session["user_id"])

        # Log transaction into database
        new_transaction_id = log_transaction(symbol, int(shares), stock_price)

        if rows_updated < 1 or new_transaction_id < 1:
            return apology("seriously", 403)

        flash("Bought!")

        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transaction_data = db.execute("SELECT symbol, shares, price, transacted_on FROM transactions WHERE user_id=:user_id ORDER BY transacted_on DESC", user_id=session["user_id"])

    return render_template("history.html", transaction_data=transaction_data)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        flash("Login successful!")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    flash("Logout successful")

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide symbol", 403)

        # Stock price response
        price_response = lookup(symbol)

        # Check if response is null
        if not price_response:
            return apology("invalid stock symbol", 403)

        # Get historical data response - handle null data in client side
        # historical_prices = filter_historical_data(chart_lookup(symbol))

        return render_template("quoted.html", name=price_response["name"], price=price_response["price"], symbol=price_response["symbol"]) #, historical_data=historical_prices)


# def filter_historical_data(json_dict):
#     """Filter the historical stock data from the json_response"""
#     filtered_data = {}

#     for day in json_dict:
#         filtered_data[day["date"]] = day["close"]

#     return filtered_data

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user id
    session.clear()

    # GET method (directing to register form)
    if request.method == "GET":
        return render_template("register.html")


    # POST method (submitting register form)
    else:
        # Ensure username is submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Ensure password is submitted
        if (request.form.get("password") == "") or (request.form.get("confirmantion") == ""):
            return apology("must provide password", 403)

        # Check if user exists in the DB
        user_check = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))
        if len(user_check) != 0:
            return apology("username already exists", 403)

        # Hash password
        hashed_pwd = generate_password_hash(request.form.get("password"))

        # Insert user into DB
        new_pk = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username=request.form.get("username"),hash=hashed_pwd)

        if new_pk > 0:
            session["user_id"] = new_pk

            flash("Registration successful!")

            return render_template("index.html")
        else:
            return apology("Oops! Something went wrong!")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        # Get list of shares user currently owns
        shares = db.execute("SELECT DISTINCT symbol FROM stocks_owned WHERE user_id=:current_id",
                            current_id=session["user_id"])

        return render_template("sell.html", shares=shares)


    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Check if symbol is provided
        if not symbol:
            return apology("must provide symbol", 403)

        # Check if number of shares has been entered
        if not shares:
            return apology("must provide shares", 403)

        # Check how many shares the user has in the database
        current_shares_row = db.execute("SELECT symbol, shares_owned FROM stocks_owned WHERE (user_id=:current_user AND symbol=:symbol)",
                                    current_user=session["user_id"], symbol=symbol)

        # If user doesn't own any shares of the stock (just in case)
        if len(current_shares_row) <= 0:
            return apology("you don't any shares of this stock", 403)

        current_shares = current_shares_row[0]["shares_owned"]

        # If the user doesn't own enough shares to make a sale
        if current_shares < int(shares):
            return apology("you don't have enough shares buddy", 403)

        # Add amount of money earned to cash
        if update_shares(symbol, current_shares, int(shares)):
            flash("Sold!")
            return redirect("/")
        else:
            return apology("i swear i don't know what's going on")

# Update shares in database
def update_shares(symbol, shares_owned, shares_to_be_sold):
    if shares_owned == int(shares_to_be_sold):
        # Delete the row
        deleted_rows = db.execute("DELETE FROM stocks_owned WHERE symbol=:symbol", symbol=symbol)

        if deleted_rows < 1:
            return apology("something went wrong", 403)

    else:
        # Update the row
        remaining_shares = shares_owned - int(shares_to_be_sold)
        updated_rows = db.execute("UPDATE stocks_owned SET shares_owned=:new_value WHERE symbol=:symbol",
                                  new_value=remaining_shares, symbol=symbol)
        if updated_rows < 1:
            return apology("something went wrong", 403)

    return add_profits(symbol, int(shares_to_be_sold))


# Add profits to current cash amount
def add_profits(symbol, shares_sold):
    # Get current price of stock
    response = lookup(symbol)

    # Check if response is null
    if not response:
        return apology("something went VERY wrong", 403)

    stock_price = response["price"]

    total_profits = stock_price * shares_sold

    # Add the profits into the db
    user_cash_updated = db.execute("UPDATE users SET cash = cash + :profit WHERE id=:current_user",
                                   profit=total_profits, current_user=session["user_id"])

    # Log transaction into database -> shares exchanged is negative
    new_transaction_id = log_transaction(symbol, shares_sold * -1, stock_price)

    return ((user_cash_updated == 1) and (new_transaction_id > 0))

# Log transaction into database
def log_transaction(symbol, shares_exchanged, stock_price):
    new_pk = db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transacted_on) VALUES (:user_id, :symbol, :shares, :price, DATETIME('now'))",
                        user_id=session["user_id"], symbol=symbol.upper(), shares=shares_exchanged, price=stock_price)
    return new_pk


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
