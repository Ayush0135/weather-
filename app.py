from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, flash
import requests
from datetime import datetime
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key
DATABASE = 'weather.db'

# ---------------- DATABASE SETUP ----------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

import random
import string


def init_db():
    with app.app_context():
        db = get_db()
        # Create table with email if not exists
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Migration: Check if email column exists, if not add it
        try:
            db.execute('SELECT email FROM users LIMIT 1')
        except sqlite3.OperationalError:
            db.execute('ALTER TABLE users ADD COLUMN email TEXT UNIQUE')
            
        db.commit()

# Initialize DB on start
if not os.path.exists(DATABASE):
    init_db()

# ---------------- AUTH DECORATOR ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

# ---------------- AUTH ROUTES ----------------
@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone() is not None:
            error = f'User {username} is already registered.'
        elif db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone() is not None:
            error = f'Email {email} is already registered.'

        if error is None:
            # Generate OTP
            otp = ''.join(random.choices(string.digits, k=6))
            
            # Store in session for verification
            session['signup_data'] = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'otp': otp
            }
            
            # Simulate sending email
            flash(f'OTP sent to {email}: {otp}') # For demo purposes
            print(f"OTP for {email}: {otp}")
            
            return redirect(url_for('verify_otp'))

        flash(error)

    return render_template('signup.html')

@app.route('/verify_otp', methods=('GET', 'POST'))
def verify_otp():
    if 'signup_data' not in session:
        return redirect(url_for('signup'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        stored_data = session['signup_data']
        
        if entered_otp == stored_data['otp']:
            # Create user
            db = get_db()
            try:
                db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                           (stored_data['username'], stored_data['email'], stored_data['password']))
                db.commit()
                
                # Auto login
                user = db.execute('SELECT * FROM users WHERE username = ?', (stored_data['username'],)).fetchone()
                session.clear()
                session['user_id'] = user['id']
                
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                flash('An error occurred. Please try again.')
                return redirect(url_for('signup'))
        else:
            flash('Invalid OTP. Please try again.')
            
    return render_template('verify_otp.html')

@app.route('/login', methods=('GET', 'POST'))
# ... (rest of login)
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- GEO CODING ----------------
def geocode(city):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 1})
    data = r.json()
    if "results" not in data:
        return None
    return data["results"][0]


# ---------------- ROUTES ----------------
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/manual")
@login_required
def manual_page():
    return render_template("manual.html")


# ---------------- WEATHER API ----------------
@app.route("/weather")
@login_required
def weather():
    city = request.args.get("city", "")
    place = geocode(city)

    if not place:
        return jsonify({"error": "City not found"}), 404

    lat = place["latitude"]
    lon = place["longitude"]

    # API Call
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": (
                "temperature_2m,precipitation,pressure_msl,"
                "relativehumidity_2m,cloudcover,windspeed_10m,winddirection_10m"
            ),
            "daily": "temperature_2m_max,temperature_2m_min",
            "current_weather": "true",
            "timezone": "auto"
        }
    )

    data = r.json()

    hourly = data["hourly"]
    current = data["current_weather"]

    times = hourly["time"]
    temps = hourly["temperature_2m"]
    precips = hourly["precipitation"]
    pressure = hourly["pressure_msl"]
    humidity = hourly["relativehumidity_2m"]
    cloud = hourly["cloudcover"]
    wind_speed = hourly["windspeed_10m"]
    wind_dir = hourly["winddirection_10m"]

    # SAFE TIME MATCH (Fixes your error)
    current_time = datetime.fromisoformat(current["time"])
    hour_times = [datetime.fromisoformat(t) for t in times]
    idx = min(range(len(hour_times)), key=lambda i: abs(hour_times[i] - current_time))

    # Tomorrow forecast
    tomorrow_min = data["daily"]["temperature_2m_min"][1]
    tomorrow_max = data["daily"]["temperature_2m_max"][1]

    return jsonify({
        "city": f"{place['name']}, {place['country']}",

        # Current weather
        "current_temp": current["temperature"],
        "current_rain": precips[idx],
        "current_pressure": pressure[idx],
        "current_humidity": humidity[idx],
        "current_cloud": cloud[idx],
        "current_wind_speed": wind_speed[idx],
        "current_wind_direction": wind_dir[idx],

        # Tomorrow
        "tomorrow_min": tomorrow_min,
        "tomorrow_max": tomorrow_max,

        # Graph data for next 24 hours
        "hour_labels": [t.split("T")[1] for t in times[idx:idx+24]],
        "hour_temps": temps[idx:idx+24],
        "hour_rain": precips[idx:idx+24]
    })


# ---------------- MANUAL PREDICTION ----------------
@app.route("/predict", methods=["POST"])
@login_required
def manual_predict():
    try:
        data = request.get_json()
        humidity = float(data.get("humidity", 0))
        pressure = float(data.get("pressure", 0))
        temp = float(data.get("temperature", 0))
        cloud = float(data.get("cloud", 0))
        wind = float(data.get("wind", 0))

        # Simple scoring logic
        score = (humidity * 0.4) + (cloud * 0.3) - (pressure * 0.1) + (wind * 0.2)

        if score > 120:
            prediction = "High chance of rainfall"
        elif score > 80:
            prediction = "Moderate chance of rainfall"
        else:
            prediction = "Low chance of rainfall"

        return jsonify({"prediction": prediction})

    except Exception as e:
        return jsonify({"error": f"Invalid Input: {str(e)}"}), 400


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    init_db() # Ensure DB is created
    app.run(debug=True, port=5001)
