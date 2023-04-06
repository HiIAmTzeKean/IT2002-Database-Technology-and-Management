from functools import wraps
from flask_cors import CORS, cross_origin
from flask import Flask, flash, redirect, request, Response, render_template, url_for, session
from models import end_point_action

# Instantiate object app
app = Flask(__name__, template_folder='templates')
# Add cross origin security
CORS(app)
app.secret_key = 'the random string'

# connect to database
from db_manager import db, setup_database,execute_sql,execute_update
if (db == None):
    app.logger.error("Not able to connect to db")
    raise Exception("ERROR")
setup_database(db)
app.logger.info("Database created and populated")

# Login wrapper
def is_login(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if "user" in session:
            return f(*args, **kwargs)
        else:
            flash("Please log in before using the system")
            return redirect(url_for("user"))
    return decorated_func

@app.route("/")
def home():
    return redirect(url_for("logout"))

@app.route('/user', methods = ['GET', 'POST'])
def user():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        record = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}' AND password = '{password}'")
        email_checker = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}'")
        if len(record) == 0 and len(email_checker) == 1:
            flash(f"You have entered the wrong password for {email}.")
            return render_template("user/login.html")
        elif len(record) == 0:
            flash("Account doesnt exist!")
            return render_template("user/login.html")
        else:
            session["user"] = email
            flash("Logged in")
        return redirect(url_for("rentals"))

    return render_template("user/login.html")
    
@app.route('/register', methods = ['POST'])
def register():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        age = request.form.get("age")

        duplicate_account = execute_sql(db,
            f"SELECT * FROM users WHERE email = '{email}'") 
        if len(duplicate_account) == 1: 
            flash(f"Account already exists for {email}!")
            return redirect(url_for("user"))
        record = execute_update(db,
            f'''
            INSERT INTO users (fname, lname, email, age, password) values
            ('{fname}', '{lname}', '{email}', {age}, '{password}');
            ''')
        db.commit()
        flash(f"Yay {fname} you now have an account!!!")
    return redirect(url_for("user"))
    
@app.route('/logout')
@is_login
def logout():
    session.pop("user", None)
    return redirect(url_for("user"))

@app.route('/profile', methods=('GET', 'POST')) #char or int
@is_login
def update_profile():
    email = session["user"]

    if request.method == 'POST':
        password = request.form['password']
        credit_card = request.form['credit_card']
        credit_card_type = request.form['credit_card_type']
        credit_card_action = request.form['credit_card_action']
        if password:
            execute_update(db,f'''
            UPDATE users 
            SET password = {password}
            WHERE email = '{email}'; 
            ''')
            db.commit()
            flash('Updated your password!')
        ## Update credit card only
        if (credit_card and credit_card_type):
            message = check_credit_card(credit_card_action, credit_card, credit_card_type, email)
            if message:
                flash(message)
            else: 
                credit_card_operation(credit_card_action, credit_card, credit_card_type, email)
                flash(f"Updated your credit card!")
        elif credit_card or credit_card_type:
            flash('Both Credit Card Number & Type required to Update!')
        elif not password and (credit_card and credit_card_type):
            flash('Nothing filled in. No changes made.')
            
    curr_credit_card_types = execute_sql(db, f'''
            SELECT * FROM credit_cards WHERE email = '{email}';
            ''')
    user = execute_sql(db, f'''
            SELECT * FROM users WHERE email = '{email}';
            ''')[0]
    return render_template('user/profile.html',
                curr_credit_card_types=curr_credit_card_types,
                user_fname=user.fname,
                user_lname=user.lname,
                user_email=user.email)

def credit_card_operation(action, number, type, email):
    if action == "UPDATE":
        execute_update(db,f'''
        UPDATE credit_cards SET type = '{type}',
        number = '{number}'
        WHERE email = '{email}';
        ''')
    elif action == "ADD":
        execute_update(db,f'''
        INSERT INTO credit_cards(type,number,email) 
        values('{type}','{number}','{email}');
        ''')
    db.commit()
    return

def check_credit_card(action, number, type, email):
    if action == "UPDATE":
        check = execute_sql(db, f'''
                SELECT * FROM credit_cards WHERE email = '{email}' AND
                type = '{type}';
                ''')
        if len(check) == 0:
            return f"Credit Card Type does not exist yet in your account. Unable to UPDATE!"
        else:
            return ""
    elif action == "ADD":
        check = execute_sql(db, f'''
                SELECT * FROM credit_cards WHERE email = '{email}' AND
                type = '{type}';       
                ''')
        if len(check):
            return f"Credit Card of {type} already exists! Unable to ADD. Try UPDATE instead."
        else:
            return ""
    db.commit()
    return


@app.route('/listings')
@is_login
def get_my_listings():
    email = session["user"]
    
    listings = execute_sql(db,
        f'''SELECT h.location, h.price, h.num_room, hr.rating, hr.date, u.username 
        FROM houses h, house_ratings hr, users u 
        WHERE u.email = h.owner_email AND 
        hr.houseid = h.id 
        ORDER BY h.location DESC'''
    )
    db.commit()
    return render_template('listings/index.html', listings=listings)
        
@app.route('/listings/create', methods = ['GET', 'POST'])
# @login_required #to add login required function --> either in user(), etc
def create_listing():
    if request.method == 'POST':
        location = request.form.get('location')
        price = request.form.get('price')
        num_room = request.form.get('num_room')
		# How do we generate random unique not null id number?
		# How do we obtain the current user's email to execute SQL command?
    if not location or not price or not num_room:
        error = 'All fields are required.'
    if error is not None:
        flash(error)
    else:
        id = generate_random_id() # function to be made
        execute_sql(db,
        f'''INSERT INTO houses (id, location, price, num_room, owner_email), 
        ('{id}','{location}', '{price}', '{num_room}, '{g.user['email']}');
        ''')
    return redirect(url_for('display_my_listings'))
    
@app.route('/rentals', methods = ['GET', 'POST'])
@is_login
def rentals():
    rental = execute_sql(db,
        f'''SELECT * FROM houses'''
    )
    return render_template('rent/index.html', rental=rental)

if __name__ == "__main__":
    app.run()