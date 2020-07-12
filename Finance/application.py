import os

# import modules that we want to use
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
# ensure that user sessions when they are logged in are not permanent
app.config["SESSION_PERMANENT"] = False
# ensure the location that we want to store the data for user sessions is going to be in the file system of the webserver we'll be running this application from (CS50 IDE)
app.config["SESSION_TYPE"] = "filesystem"
# we would like to enable sessions for this particular flask web app
Session(app)

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
def index():
    """Show portfolio of stocks"""

    # call my send to index, and store the variables it returns into owned_stock, cash_amoun and net_worth
    owned_stock, cash_amount, net_worth = send_to_index()

    # for debugging
    # print(owned_stock)
    # print(cash_amount_dict)
    # print(stock_dict)

    # re-render the https://finance.cs50.net/ homepage to display the newly modified owned_stock list of dicts
    return render_template("index.html", owned_stock=owned_stock, cash_amount=usd(cash_amount), net_worth=net_worth)

# app route to buy stock
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST (as by submitting a form via POST)
    else:

        # list of all potential errors that can be rendered on the buy html
        errors = ["Must provide a valid stock symbol", "Must provide a valid count of shares", "The count of shares must be numeric", "Sorry, thats not a valid stock ID", "Sorry, insufficient money to do that"]


        # Extract the current logged in users ID from the session["user_id"] dict & store it inside of "user_id" to use below
        user_id = session["user_id"]

        # Ensure stock symbol were submitted
        if not request.form.get("symbol"):
            return render_template("buy.html", errors=errors[0])

        # Ensure shares were submitted
        if not request.form.get("shares"):
            return render_template("buy.html", errors=errors[1])

        # Take the stock symbol & amount of shares the user inputed in the rendered HTML page
        stock_symbol = request.form.get("symbol")
        count_shares = request.form.get("shares")

        # If the users input in the "amount" field of the rendered HTML form is not numeric, insert "the count of shares must be numeric" error into active errors list
        if not count_shares.isdigit():
            return render_template("buy.html", errors=errors[2])


        # Convert collected "count_shares" as a string, convert it into an int + Run the lookup() function (from helpers.py) against the "stock_symbol" collected from the user
        num_of_shares = int(count_shares)
        stock_dict = lookup(stock_symbol)

        # If the stock_dict that was returned by lookup() has a value of 'None' insert "Sorry, insert "thats not a valid stock ID" error into active errors list
        if stock_dict == None:
            return render_template("buy.html", errors=errors[3])


        # Extract the name, price & symbol from this dictionary that was returned. Then store these values in seperate variables
        company_name = stock_dict["name"]
        stock_price = stock_dict["price"]
        stock_symbol = stock_dict["symbol"]
        # Multiply the "stock_price" we just got in that variable against the value of "count_shares" the user intends to purchase + store this value in a new variable, "stock_multiplied"
        stock_multiplied = num_of_shares * stock_price

        # Query db for the current "user_id" we previously extracted above. Then extract the "cash" column from this users row inside of the users table, ensuring they can afford the stock. this is returned as a dict
        cash_amount_dict = db.execute("SELECT cash FROM users WHERE id = :userid;",
                                      userid=user_id)
        # For debugging:
        # print(user_id)
        # print(cash_amount_dict)

        # Extract the "cash" amount from this dict, thats inside of the first element of a list [0] of dicts, & then, the "cash" column from inside that dict: ["cash"]
        user_cash_amount = cash_amount_dict[0]["cash"]

        # If: value of "stock_multiplied" is > the "Cash" amount in the column of the Users table inside our db, for this current user account being queried, insert "Sorry, insufficient money to do that" error into active errors list
        if stock_multiplied > user_cash_amount:
            return render_template("buy.html", errors=errors[4])


        # Subtract "stock_multiplied" from "user_cash_amount", to get a leftover new cash value we'll want to re-inject into the cash column for this user inside the users table
        cash_leftover = user_cash_amount - stock_multiplied

        # string to return as a boostrap message in the index.html
        bought = ["Bought!"]

        # Query db for the current session["user_id"], then, UPDATE the existing cash amount in the users table for this current user to == "cash_leftover"
        db.execute("UPDATE users SET cash = :cash WHERE id = :userid",
		    	    userid=user_id, cash=cash_leftover)

        # Verify if the user already owns stock
        owned_stock = db.execute("SELECT amount FROM portfolio WHERE id = :userid AND symbol = :stocksymbol;",
                                 userid=user_id, stocksymbol=stock_symbol)

        # If owned_stock is an empty list containing no dicts, indicating that user has no existing entries of that stock type in the db
        if owned_stock == []:

            # INSERT the "count_shares" value and the "stock_symbol" collected for the current user_id in the "symbol" and "amount" columns of the PORTFOLIO table in our db
            db.execute("INSERT INTO portfolio (id, symbol, amount) VALUES (?, ?, ?);",
            user_id, stock_symbol, count_shares)

        else:


            # Extract the "amount" from this "owned_stock" dictionary that was returned, & store these values in seperate variables
            owned_dict_amount = owned_stock [0]["amount"]
            added_amount = owned_dict_amount + num_of_shares

            # Update the portfolio table in our db with the users newly collected "added_amount" from this script WHERE the id in the db matches the user ID in this script && the symbol in the db matches "stock_symbol" in the script
            db.execute("UPDATE portfolio SET amount =:amount WHERE id = :userid AND symbol = :symbol;",
                        userid=user_id, symbol=stock_symbol, amount=added_amount)

        # cann my record_history() function to insert the transaction info we just performed in this buy branch into my db
        record_history(user_id, stock_symbol, num_of_shares, stock_price, "buy")

        # call my send to index, and store the variables it returns into owned_stock, cash_amoun and net_worth
        owned_stock, funct_cash_amount, net_worth = send_to_index()

        # for debugging
        # print(owned_stock)
        # print(cash_amount_dict)
        # print(stock_dict)

        # render the blue success login banner upon login
        return render_template("index.html", bought=bought[0], owned_stock=owned_stock, cash_amount=usd(funct_cash_amount), net_worth=usd(net_worth))

# pull all the info from our 'history' table and pass it into a html file.
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Extract the current logged in users ID from the session["user_id"] dict & store it inside of "user_id" to use below
    user_id = session["user_id"]

    # grab all of the rows and colums inside of the history table (but only for this user) and store them in a list of dicts
    history_dict = db.execute("SELECT * FROM history WHERE id = :userid;",
                                userid=user_id)

    # re-render the https://finance.cs50.net/ homepage to display the transtaction history in the history_dict
    return render_template("history.html", history_dict=history_dict)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # list of all potential errors that can be rendered on the buy html
        errors = ["Must provide a username", "Must provide password", "Invalid username and/or password"]

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", errors=errors[0])

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", errors=errors[1])

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", errors=errors[2])

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("quote.html")

    # User reached route via POST (as by submitting a form via POST)
    else:

        # list of all potential errors that can be rendered on the buy html
        errors = ["Must provide a valid stock symbol", "Sorry, thats not a valid stock ID"]

        # Ensure stock symbol was not submitted
        if not request.form.get("symbol"):
            return render_template("quote.html", errors=errors[0])

        # take the stock symbol the user inputed in the rendered HTML page and store it inside of a variable
        stock_symbol = request.form.get("symbol")

        # run the lookup() function (from helpers.py) against the stock_symbol collected from the user & get a dict for valid stock symbols OR 'None' for invalid stock symbols
        stock_dict = lookup(stock_symbol)

        # if stock_dict that was returned has a value of 'None'
        if stock_dict == None:
            return render_template("quote.html", errors=errors[1])

        # extract the name, price and symbol from this dictionary that was returned, and store these values in seperate variables
        company_name = stock_dict["name"]
        stock_price = stock_dict["price"]
        stock_symbol = stock_dict["symbol"]

        # renders the original quote page + returns the values seperately from our stock_dict to the HTML page to this page being rendered here when it is needed
        return render_template("quote_result.html" , returned_name=company_name, returned_price=stock_price, returned_symbol=stock_symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "GET":
        return render_template("register.html")

    else:

        # list of all potential errors that can be rendered on the buy html
        errors = ["Must provide username", "Must provide password", "Password and confirmation must match", "Username is taken"]

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("register.html", errors=errors[0])

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("register.html", errors=errors[1])

        # compare strings in both password and confimration fields, if they dont match, throw an error
        elif request.form.get("password") != request.form.get("confirmation"):
            return render_template("register.html", errors=errors[2])

        # Query the db & check if the username they typed in at username=request.form.get, is of another user that exists in our database
        # if these match with an existing user in our db, a list of dicts will be returned, each dict containing the name of the existing user that matched as a "value" in each keyvaluepair
        rows = db.execute("SELECT username FROM users WHERE username = :username;",
            username=request.form.get("username"))

        # if rows is returned as an empty list, not containing any dictionaries with names in them, there is no existing user, is a list of any lengh apart from 0 is returned, a user already exists
        if len(rows) != 0:
            return render_template("register.html", errors=errors[3])

    # collect users password they entered in the form to hash
    password_var = request.form.get("password")

    # hash this password
    hash_pw = generate_password_hash(password_var)

    # collect the username from this HTMl form
    user_name = request.form.get("username")

    # if all of the above passes, insert this new user + pw hash into our users table in our DB
    db.execute("INSERT INTO users(username,hash) VALUES (?,?);",
        user_name, hash_pw)

    success_login = ["Registered!"]

    # select the username from our db as the current session and store it as the current users logged in session, it's the first index in the list of dicts returned
    session["user_id"] = db.execute("SELECT id FROM users WHERE username = :username;",
                          username=user_name) [0]["id"]

    # Query db for the current "user_id" who's currently logged into this session. Then extract the "cash" column from this users row inside of the users table, this is returned as a list of dicts
    cash_amount_dict = db.execute("SELECT cash FROM users WHERE id = :userid;",
                                    userid=session["user_id"])

    # Extract the "cash" amount from this dict, thats inside of the first element of a list [0] of dicts, & then, the "cash" column from inside that dict: ["cash"]
    cash_amount = float(cash_amount_dict[0]["cash"])

    # set the net worth and make it == to the inital cash amount
    net_worth = cash_amount

    # call owned_stock and store the variables it returns into these vars
    owned_stock, cash_amount, net_worth = send_to_index()

    # render the blue success login banner upon login
    return render_template("index.html", success_login=success_login[0], cash_amount=usd(cash_amount), net_worth=usd(net_worth))


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":

        # Extract the current logged in users ID from the session["user_id"] dict & store it inside of "user_id" to use below
        user_id = session["user_id"]

        # backend code to get the stock_symbol menu working
        dropdown_dict = db.execute("SELECT symbol FROM portfolio WHERE id = :userid;", userid=user_id)

        # return the dropdown dict to be rendered with the THML
        return render_template("sell.html", dropdown_dict=dropdown_dict)

    # User reached route via POST (as by submitting a form via POST)
    else:

        # Extract the current logged in users ID from the session["user_id"] dict & store it inside of "user_id" to use below
        user_id = session["user_id"]

        # list of all potential errors that can be rendered on the buy html
        errors = ["Must provide a valid stock symbol", "Must provide a valid count of shares", "The count of shares must be numeric", "Sorry, thats not a valid stock ID", "Sorry, you dont own enough of that stock to sell"]

        # backend code to get the stock_symbol menu working
        dropdown_dict = db.execute("SELECT symbol FROM portfolio WHERE id = :userid;", userid=user_id)

        # Ensure stock symbol were submitted
        if not request.form.get("symbol"):
            return render_template("sell.html", errors=errors[0], dropdown_dict=dropdown_dict)

        # Ensure shares were submitted
        if not request.form.get("shares"):
            return render_template("sell.html", errors=errors[1], dropdown_dict=dropdown_dict)

        # take the stock symbol and count of that stock from the users HTML
        stock_symbol = request.form.get("symbol")
        count_shares = request.form.get("shares")

        # If the users input in the "amount" field of the rendered HTML form is not numeric, throw an error
        if not count_shares.isdigit():
            return render_template("sell.html", errors=errors[2], dropdown_dict=dropdown_dict)

        # Convert collected "count_shares" as a string, convert it into an int & store it inside a num_of_shares variable of type int
        num_of_shares = int(count_shares)

        # Run the lookup() function (from helpers.py) against the "stock_symbol" collected from the user &. This gets a dict for valid stock symbols OR 'None' for invalid stock symbols
        stock_dict = lookup(stock_symbol)

        # If the stock_dict that was returned by lookup() has a value of 'None'
        if stock_dict == None:
            return render_template("sell.html", errors=errors[3], dropdown_dict=dropdown_dict)

        # Extract the name, price & symbol from this dictionary that was returned. Then store these values in seperate variables
        company_name = stock_dict["name"]
        stock_price = stock_dict["price"]
        stock_symbol = stock_dict["symbol"]

        # Multiply the "stock_price" we just got in that variable against the value of "count_shares" the user intends to sell + store this value in a new variable, "stock_multiplied" to be used later to add cash
        stock_multiplied = num_of_shares * stock_price

        # Query db for the current "user_id" we previously extracted above. Then extract the "cash" column from this users row inside of the users table, ensuring they can afford the stock. this is returned as a dict
        cash_amount_dict = db.execute("SELECT cash FROM users WHERE id = :userid;",
                          userid=user_id)

        # Extract the "cash" amount from this dict, thats inside of the first element of a list [0] of dicts, & then, the "cash" column from inside that dict: ["cash"]
        user_cash_amount = cash_amount_dict[0]["cash"]

        # Lookup the amount of each stock the user owns from portfolio table
        stocks_owned_dict = db.execute("SELECT * FROM portfolio WHERE id = :userid;",
										userid=user_id)

        # if count_shares for the current stock_symbol exceeds the amounf of stocks the user owns for that returned in stocks_owned_dict
        for dictionary in stocks_owned_dict:

            if stock_symbol == dictionary["symbol"] and num_of_shares > dictionary["amount"]:
                return render_template("sell.html", errors=errors[4], dropdown_dict=dropdown_dict)

            elif stock_symbol == dictionary["symbol"]:
                shares_from_dict = dictionary["amount"]

        # Add the amount of the stocks the user just sold to the value of cash they own
        cash_after_sell = user_cash_amount + stock_multiplied

        # subtract how many shares this user selected of this type in the HTML page
        shares_after = shares_from_dict - num_of_shares

        # string to return as a boostrap message in the index.html
        sold = ["Sold!"]

        # Update the users table in our db with the new value of cash after they sell their stocks
        db.execute("UPDATE users SET cash =:cash_after_sell WHERE id = :userid;",
                    userid=user_id, cash_after_sell=cash_after_sell)

        # Update portfolio table in our db with the users newly collected "added_amount"
        db.execute("UPDATE portfolio SET amount =:amount WHERE id = :userid AND symbol = :symbol;",
                    userid=user_id, symbol=stock_symbol, amount=shares_after)

        # cann my record_history() function to insert the transaction info we just performed in this sell branch into my db
        record_history(user_id, stock_symbol, num_of_shares, stock_price, "sell")

        # if the amount of shares for thi stock after it is sold is 0, selete that stock from the useers portfolio row in the db
        if shares_after == 0:
            db.execute("DELETE FROM portfolio WHERE id = :userid AND symbol = :symbol;",
                       userid=user_id, symbol=stock_symbol)

        # call my send to index, and store the variables it returns into owned_stock, cash_amoun and net_worth
        owned_stock, funct_cash_amount, net_worth = send_to_index()

        # render the blue success login banner upon login
        return render_template("index.html", sold=sold[0], owned_stock=owned_stock, cash_amount=usd(funct_cash_amount), net_worth=usd(net_worth))


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# function that will be call after a transaction is made in our db in buy or sell. pass in the following as paramaters from buy() or sell() to this function:
def record_history(user_id, stock_symbol, num_of_shares, stock_price, buy_or_sell):

    # insert these new extracted values into our DB and also record the current timestamp this happened at
    db.execute("INSERT into 'history' ('id', 'symbol', 'shares', 'price', 'buyvssell') VALUES (?, ?, ?, ?, ?);",
                user_id, stock_symbol, num_of_shares, stock_price, buy_or_sell)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# for passing a rendered index html with a "bought!" or "sold!" banner
def send_to_index():

    # Extract the current logged in users ID from the session["user_id"] dict & store it inside of "user_id" to use below
    user_id = session["user_id"]

    # Query db for the current "user_id" who's currently logged into this session. Then extract the "cash" column from this users row inside of the users table, this is returned as a list of dicts
    cash_amount_dict = db.execute("SELECT cash FROM users WHERE id = :userid;",
                                    userid=user_id)

    # Select everything from the "portfolio" table & store it in a list of dicts, "owned_stocks"
    owned_stock = db.execute("SELECT * FROM portfolio WHERE id = :userid;",
                                userid=user_id)

    # Extract the "cash" amount from this dict, thats inside of the first element of a list [0] of dicts, & then, the "cash" column from inside that dict: ["cash"]
    cash_amount = float(cash_amount_dict[0]["cash"])

    # set the added stock value to 0 initally
    added_total_stock_value = 0

    # loop through each index of the list containing dicts in owned_stocks
    for dictionary in owned_stock:

        # extract the amount of the stock in this dict the user currently owns + run the lookup() function against the "symbol" in this current dict being looped through
        stock_amount =  dictionary["amount"]
        stock_dict = lookup(dictionary["symbol"])

    	# extract the "price" out of the returned dictionary from lookup() for this current stock symbol
        stock_company_name = stock_dict["name"]
        stock_price = stock_dict["price"]
        stock_symbol = stock_dict["symbol"]

    	# take the "price" value of this current stock multipled by the number of shares of this stock this user owns, to show the total value of each holding. store this in a new variable "total_value"
        total_stock_value = stock_price * stock_amount
        added_total_stock_value += total_stock_value

        # convert total_stock_value to USD
        total_stock_value = usd(total_stock_value)

        # inject this new "total_value" of this holding back into the "owned_stocks" dict as a new key + value
        dictionary["total"] = total_stock_value
        dictionary["name"] = stock_company_name
        dictionary["price"] = stock_price

    # create a overall net worth = to this users stocks + cash amounts added together
    net_worth = added_total_stock_value + cash_amount

    # return the variables grabbed from this function, into where they are called
    return owned_stock, cash_amount, net_worth
