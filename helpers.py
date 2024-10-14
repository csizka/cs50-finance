import csv
import datetime
import pytz
import requests
import urllib
import uuid
import sqlite3

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, username, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message), username=username), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(
            url,
            cookies={"session": str(uuid.uuid4())},
            headers={"Accept": "application/json", "User-Agent": request.headers.get("User-Agent")},
        )
        response.raise_for_status()

        price = response.json()["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"][-1]

        return {"price": price, "symbol": symbol}
    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

"https://query1.finance.yahoo.com/v7/finance/download/NFLX?period1=1723413600&period2=1723795612&interval=1d&events=history&includeAdjustedClose=true"

def execute_select(db: sqlite3.Connection, statement: str, data: list[any] = []):
    execute_res = db.execute(statement, data)
    col_names = [ col_desc[0] for col_desc in list(execute_res.description) ]
    records = execute_res.fetchall()
    res = [ dict(zip(col_names, record)) for record in records ]
    return res

def get_userinfo(db, user_id):
    user = execute_select(db, """
                            SELECT *
                            FROM users
                            WHERE id = ?
    """, [user_id])
    if len(user) != 1:
        session.clear()
        return redirect("/login")
    return user