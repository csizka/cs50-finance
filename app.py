import json
import os

import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, execute_select, get_userinfo

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = sqlite3.connect(database = "finance.db", autocommit = True, check_same_thread = False)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    cash = user[0]["cash"]
    username = user[0]["username"]
    total_worth = cash
    shares = execute_select(db, """
                         SELECT symbol, amount
                         FROM stock_balance
                         JOIN symbols
                         ON symbol_id = symbols.id
                         WHERE user_id = ?
                         AND amount > 0
    """, [user_id])
    portfolio = []
    for share in shares:
        share_details = {
            "symbol": share["symbol"],
            "amount": share["amount"],
            "price": lookup(share["symbol"])["price"],
            "worth": lookup(share["symbol"])["price"] * share["amount"]
        }
        portfolio.append(share_details)
        total_worth += share_details["worth"]

    action = session["action"]
    session["action"] = None
    if action:
        flash(action)
    deposits = execute_select(db, """
                         SELECT SUM(amount) as sum
                         FROM cash_transactions
                         WHERE user_id = ?
    """, [user_id])

    if len(deposits) != 1:
        return apology("unexpected error", 400)

    deposit = deposits[0]["sum"]
    gain = total_worth - deposit

    return render_template("index.html", total_amount=total_worth, stocks=portfolio, cash=cash, share=total_worth - cash, gain=gain, username=username)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    session["action"] = None
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    username = user[0]["username"]

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", username)

        symbol = request.form.get("symbol").upper()

        if lookup(symbol) == None:
            return apology("non-existent symbol", username)

        if not request.form.get("shares"):
            return apology("must provide number of shares to buy", username)

        share = request.form.get("shares")

        try:
            share = int(share)
        except ValueError:
            return apology("must provide number of shares to buy in digits", username)

        if share <= 0:
            return apology("must provide a positive number of shares to buy", username)

        stock_price = lookup(symbol)["price"]
        full_price = stock_price * share
        budget = user[0]["cash"]

        if budget < full_price:
            return apology("not enough funds", username)

        remaining_budget = budget - full_price

        symbol_data = execute_select(db, "SELECT * FROM symbols WHERE symbol = ?", [symbol])

        if len(symbol_data) == 0:
            db.execute("INSERT INTO symbols (symbol) VALUES (?) ", [symbol])
            symbol_data = execute_select(db, "SELECT * FROM symbols WHERE symbol = ?", [symbol])

        symbol_id = symbol_data[0]["id"]
        db.execute("UPDATE users SET cash = ? WHERE id = ? ", [remaining_budget, user_id])
        db.execute("INSERT INTO purchases (user_id, symbol_id, amount, price) VALUES (?,?,?,?) ",
                   [user_id, symbol_id, share, stock_price])

        if len(execute_select(db, "SELECT * FROM stock_balance WHERE symbol_id = ? AND user_id = ?", [symbol_id, user_id])) == 0:
            db.execute(
                "INSERT INTO stock_balance (user_id, symbol_id, amount) VALUES (?,?,?)", [user_id, symbol_id, 0])

        db.execute("UPDATE stock_balance SET amount = amount + ? WHERE user_id = ? AND symbol_id = ? ",
                   [share, user_id, symbol_id])

        action = f"Successfully bought {share} Share(s) of {symbol} for ${full_price} (${stock_price}/ Share)."
        session["action"] = action

        return redirect("/")

    else:
        return render_template("buy.html", username=username)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    session["action"] = None
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    username = user[0]["username"]

    purchases = execute_select(db, """
                         SELECT
                            RANK() OVER(ORDER BY time) AS count,
                            symbol,
                            CASE WHEN amount > 0 THEN "Bought" ELSE "Sold" END AS type,
                            ABS(amount) AS amount,
                            price,
                            time
                         FROM purchases
                         JOIN symbols
                         ON symbol_id = symbols.id
                         WHERE user_id = ?
                         AND amount != 0
                         ORDER BY time DESC
    """, [user_id])

    transactions = execute_select(db, """
                         SELECT
                            RANK() OVER(ORDER BY time) AS count,
                            CASE WHEN amount > 0 THEN "Deposit" ELSE "Withdrawal" END AS type,
                            ABS(amount) AS amount,
                            SUM(amount) OVER(ORDER BY time ROWS UNBOUNDED PRECEDING) AS total,
                            time
                         FROM cash_transactions
                         WHERE user_id = ?
                         AND amount != 0
                         ORDER BY time DESC
    """, [user_id])

    return render_template("history.html", purchases=purchases, transactions=transactions, username=username)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted 2 times
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password 2 times", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("confirmation must match password", 400)
        
        # Query database for username
        rows = execute_select(db, 
            "SELECT * FROM users WHERE username = ?", [request.form.get("username")]
        )

        # Ensure username does not exist
        if len(rows) != 0:
            return apology("username already taken", 400)

        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", [username, hash])
        user = execute_select(db, "SELECT * FROM users WHERE username = ?", [username])
        user_id = user[0]["id"]
        db.execute("INSERT INTO cash_transactions (user_id, amount) VALUES (?, 10000)", [user_id])

        # Remember which user has logged in
        session["user_id"] = user_id
        action = f"Successfully logged in as {username}."
        session["action"] = action
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = execute_select(db,
            "SELECT * FROM users WHERE username = ?", [request.form.get("username")]
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        action = f"Successfully logged in as {rows[0]["username"]}."
        session["action"] = action
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    session["action"] = None

    user_id = session["user_id"]
    user = get_userinfo(db, user_id)

    username = user[0]["username"]

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", username)

        symbol = request.form.get("symbol")

        if lookup(symbol) == None:
            return apology("non-existent symbol", username)

        price = lookup(symbol)["price"]
        symbol = symbol.upper()

        return render_template("quoted.html", price=price, symbol=symbol, username=username)

    else:
        return render_template("quote.html", username=username)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    session["action"] = None
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    username = user[0]["username"]

    stocks = execute_select(db, """
        SELECT symbol, amount
        FROM stock_balance sb
        JOIN symbols s
        ON sb.symbol_id = s.id
        WHERE user_id = ?
        AND amount > 0
        ORDER BY amount DESC""", [user_id])

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", username)

        symbol = request.form.get("symbol").upper()

        if lookup(symbol) == None:
            return apology("non-existent symbol", username)

        if not request.form.get("shares"):
            return apology("must provide number of shares to sell", username)

        share_to_sell = request.form.get("shares")

        try:
            share_to_sell = int(share_to_sell)
        except ValueError:
            return apology("must provide number of shares to sell in digits", username)

        if share_to_sell <= 0:
            return apology("must provide a positive number of shares to sell", username)

        balance = execute_select(db, """
            SELECT symbol_id, amount
            FROM stock_balance sb
            JOIN symbols s
            ON sb.symbol_id = s.id
            WHERE user_id = ?
            AND symbol = ?""", [user_id, symbol])

        if len(balance) != 1:
            return apology("unexpected error", username)

        budget = balance[0]["amount"]
        symbol_id = balance[0]["symbol_id"]

        if budget < share_to_sell:
            return apology("not enough stocks", username)

        remaining_stocks = budget - share_to_sell
        stock_price = lookup(symbol)["price"]
        full_price = stock_price * share_to_sell

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ? ", [full_price, user_id])
        db.execute("INSERT INTO purchases (user_id, symbol_id, amount, price) VALUES (?,?,?,?) ",
                   [user_id, symbol_id, 0 - share_to_sell, stock_price])

        db.execute("UPDATE stock_balance SET amount = ? WHERE user_id = ? AND symbol_id = ? ",
                   [remaining_stocks, user_id, symbol_id])
        action = f"Successfully sold {share_to_sell} Share(s) of {symbol} for ${full_price} (${stock_price} / Share)."
        session["action"] = action

        return redirect("/")

    else:
        return render_template("sell.html", stocks=stocks, username=username)


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    session["action"] = None
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    username = user[0]["username"]
    if request.method == "POST":

        if not request.form.get("withdraw"):
            return apology("must provide amount", username)

        amount = request.form.get("withdraw")

        try:
            amount = int(amount)
        except ValueError:
            return apology("must provide number as amount to withdraw", username)

        if amount <= 0:
            return apology("must provide a positive number as amount to withdraw", username)

        user_id = session["user_id"]
        user = get_userinfo(db, user_id)

        budget = user[0]["cash"]

        if budget < amount:
            return apology("not enough funds", username)

        remaining_budget = budget - amount

        db.execute("UPDATE users SET cash = ? WHERE id = ? ", [remaining_budget, user_id])
        db.execute("INSERT INTO cash_transactions (user_id, amount) VALUES (?,?)", [user_id, amount * -1])

        action = f"${amount} withdrawal successful, current balance: ${remaining_budget}."
        session["action"] = action

        return redirect("/")

    else:
        budget = user[0]["cash"]

        return render_template("withdraw.html", budget=budget, username=username)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    session["action"] = None
    user_id = session["user_id"]
    user = get_userinfo(db, user_id)
    username = user[0]["username"]
    budget = user[0]["cash"]
    
    if request.method == "POST":

        if not request.form.get("deposit"):
            return apology("must provide amount", username)

        amount = request.form.get("deposit")

        try:
            amount = int(amount)
        except ValueError:
            return apology("must provide a number as amount to deposit", username)

        if amount <= 0:
            return apology("must provide a positive number as the amount to deposit", username)

        new_budget = budget + amount

        if new_budget > 9223372036854775807:
            return apology("budget exceeded", username)

        db.execute("UPDATE users SET cash = ? WHERE id = ? ", [new_budget, user_id])
        db.execute("INSERT INTO cash_transactions (user_id, amount) VALUES (?,?)", [user_id, amount])

        action = f"${amount} deposit successful, current balance: ${new_budget}."
        session["action"] = action

        return redirect("/")

    else:
        return render_template("deposit.html", budget=budget, username=username)
