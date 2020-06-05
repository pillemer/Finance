# export API_KEY=pk_112fbee9f7da4459a327955b98b73fd7

import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, day_time

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

#-----------------------------------------------------INDEX-------------------------------------------------
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Look for number of shares from each stock for the user
    holdings = db.execute("SELECT symbol, SUM(amount) FROM (SELECT * FROM history WHERE user_id = :session) GROUP BY symbol", session = session['user_id'])

    # iterate over every entry in folio and append to a list including a lookup for current price
    folio = []
    shares_value = 0
    for entry in holdings:
        quote = lookup(entry['symbol'])
        value = entry['SUM(amount)'] * quote['price']
        shares_value += value
        folio.append((entry['symbol'],quote['name'], entry['SUM(amount)'],usd(quote['price']), usd(value)))

    # Store user's current cash in variable
    rows = db.execute("SELECT cash FROM users WHERE id = :session", session = session['user_id'])
    cash = round(rows[0]["cash"], 2)

    # calculate the total
    tot_sum = usd(round(shares_value + cash, 2))
    return render_template('index.html', folio = folio, cash = usd(cash), tot_sum = tot_sum)

#-----------------------------------------------------BUY---------------------------------------------------
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Store symbol in variable
        symbol = request.form.get("symbol").upper()

        # Ensure symbol was submitted
        if not symbol:
            return apology("Please provide stock symbol", 403)

        # ensure share amount is an integer and store in variable if so
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Please provide a valid number.", 403)

        # Ensure positive interger was submitted
        if (not shares) or (shares <= 0):
            return apology("Please provide a valid share amount.", 403)

        else:
            # Store user's current cash in variable
            rows = db.execute("SELECT cash FROM users WHERE id = :session", session = session['user_id'])
            avail_cash = rows[0]["cash"]

            # lookup the stock symbol and insert name and price to variable
            result = lookup(symbol)
            if not result:
                return apology("No result for this stock. Please try again.", 403)
            else:
                name=result['name']
                share_price = result['price']
                total_price = round((share_price * shares), 3)

            # Check that user has enough cash to buy stock (stock price * shares <= cash)
            if avail_cash < total_price:
                return apology('not enough cash.', 403)

            else:
                # update DB.users new cash amount
                change = avail_cash - total_price
                db.execute("UPDATE users SET cash = :change WHERE id = :session", change = change, session = session['user_id'])

                # get current date and time
                date, time = day_time()

                # update history table for the user with stock name, price at time of purchase, and total amount paid, time/date
                db.execute("""INSERT INTO history (user_id, symbol, amount, share_price, date, time)
                               VALUES (:user_id, :symbol, :amount, :price, :date, :time)""",
                            user_id = session['user_id'], symbol = symbol, amount = shares, price = share_price, date = date, time =time)

            return render_template("bought.html", name=name, symbol=symbol, shares=shares, total_price=total_price)
    else:
        return render_template("buy.html")

#-----------------------------------------------------HISTORY---------------------------------------------------
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # create a list of all the actions this user has taken
    user_history = db.execute("SELECT * FROM history WHERE user_id = :session", session = session['user_id'])

    return render_template("history.html", user_history = user_history)

#-----------------------------------------------------LOGIN-----------------------------------------------------
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

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

#-----------------------------------------------------LOGOUT---------------------------------------------------
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

#-----------------------------------------------------QUOTE----------------------------------------------------
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Store symbol in variable
        symbol = request.form.get("symbol").upper()

        # Ensure stock name was submitted
        if not symbol:
            return apology("Please provide a valid stock symbol.", 403)

        else:
            result = lookup(symbol)
            if not result:
                return apology("Please provide a valid stock symbol", 403)
            else:
                return render_template('quoted.html', name=result['name'], price=usd(result['price']), symbol=result['symbol'])

    else:
        return render_template("quote.html")

#-----------------------------------------------------REGISTER---------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password confirmation has been submitted
        elif not request.form.get("password_confirm"):
            return apology('Please confirm your password', 403)

        # Check both passwords match
        elif request.form.get("password") != request.form.get("password_confirm"):
            return apology('Passwords did not match. Please try again.', 403)

        # Hash and store password in variable
        user_pass = generate_password_hash(request.form.get("password"))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Check if username already exists
        if len(rows) >= 1:
            return apology("Username already exists. Please choose another.", 403)

        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
                               username=request.form.get("username"), password=user_pass)

        # Redirect user to home page
        return redirect("/login")

    else:
        return render_template('register.html')

#-----------------------------------------------------SELL--------------------------------------------------
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # Look for number of shares from each stock for the user
        holdings = db.execute("SELECT symbol, SUM(amount) FROM (SELECT * FROM history WHERE user_id = :session) GROUP BY symbol", session = session['user_id'])

        # create list of available symbols
        shares = []
        for stock in holdings:
            shares.append(stock['symbol'])

        # Store selected symbol in variable
        symbol = request.form.get("symbol")

        # Ensure symbol was submitted
        if not symbol:
            return apology("Please select a stock symbol", 403)

        # store share amount in variable
        amount = int(request.form.get("shares"))

        # check amount to be sold doesn't exceeed amount owned
        owned = db.execute("SELECT SUM(amount) FROM (SELECT * FROM history WHERE user_id = :session AND symbol = :symbol)", session = session['user_id'], symbol = symbol)

        if amount > owned[0]['SUM(amount)']:
            return apology('You do not own that many shares.', 403)

        # lookup the stock symbol and insert name and price to variable
        result = lookup(symbol)
        if not result:
            return apology("No result for this stock. Please try again.", 403)
        else:
            name=result['name']
            share_price = result['price']
            print(f'this is shares: {shares} and this is share price: {share_price}')
            total_price = round((share_price * amount), 3)

        # update cash
        db.execute("UPDATE users SET cash = cash + :change WHERE id = :session", change = total_price, session = session['user_id'])

        # get current date and time
        date, time = day_time()

        # update history table for the user with stock name, price at time of purchase, and total amount paid, time/date
        db.execute("""INSERT INTO history (user_id, symbol, amount, share_price, date, time)
                       VALUES (:user_id, :symbol, :amount, :price, :date, :time)""",
                    user_id = session['user_id'], symbol = symbol, amount = (amount*(-1.0)), price = share_price, date = date, time =time)

        return render_template('sold.html', shares = shares, amount = amount, name = name, symbol = symbol, total_price = total_price)

    else:
        # Look for number of shares from each stock for the user
        holdings = db.execute("SELECT symbol, SUM(amount) FROM (SELECT * FROM history WHERE user_id = :session) GROUP BY symbol", session = session['user_id'])
        shares = []
        for stock in holdings:
            shares.append(stock['symbol'])

        return render_template('sell.html', shares = shares)

#-----------------------------------------------------------------------------------------------------------
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
