import os
import base64
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import unquote
from sqlalchemy import inspect # Import inspect

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_here') # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Initialization (Runs when app starts) ---
with app.app_context():
    inspector = inspect(db.engine) # Create an inspector
    # Check if any table exists (e.g., Config table) as a heuristic
    if not inspector.has_table(Config.__tablename__): # Use inspector.has_table
        print("Database tables not found. Creating tables...")
        db.create_all()
        print("Tables created.")

# --- Database Models ---
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot = db.Column(db.String(100), unique=True, nullable=False)
    booked_by = db.Column(db.String(100), nullable=True) # OB's name

# --- Helper Functions ---
def get_app_data():
    ob_names_config = Config.query.filter_by(key='ob_names').first()
    time_slots_config = Config.query.filter_by(key='time_slots').first()
    schedule_items = Schedule.query.all()

    schedule_dict = {item.slot: item.booked_by for item in schedule_items}

    return {
        'ob_names': ob_names_config.value if ob_names_config else [],
        'time_slots': time_slots_config.value if time_slots_config else [],
        'schedule': schedule_dict
    }

# --- Routes ---
@app.route('/')
def admin_page():
    data = get_app_data()
    return render_template('index.html', data=data)

@app.route('/setup', methods=['POST'])
def setup_schedule():
    req_data = request.json
    ob_names = req_data.get('ob_names', [])
    time_slots = req_data.get('time_slots', [])

    # Clear old data
    db.session.query(Config).delete()
    db.session.query(Schedule).delete()

    # Save new config
    db.session.add(Config(key='ob_names', value=ob_names))
    db.session.add(Config(key='time_slots', value=time_slots))

    # Create new schedule slots
    for slot in time_slots:
        db.session.add(Schedule(slot=slot, booked_by=None))
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'スケジュールが設定されました。'})

@app.route('/booking')
def booking_page():
    ob_id = request.args.get('ob')
    if not ob_id: return "エラー: 招待リンクが無効です。", 400
    try:
        ob_name = unquote(base64.b64decode(ob_id).decode('utf-8'))
    except Exception: return "エラー: 招待リンクの形式が正しくありません。", 400

    data = get_app_data()
    if ob_name not in data.get('ob_names', []): return "エラー: あなたは招待されていません。", 403

    return render_template('booking.html', ob_name=ob_name, schedule=data['schedule'])

@app.route('/book', methods=['POST'])
def book_slot():
    req_data = request.json
    ob_name = req_data.get('ob_name')
    slot_to_book = req_data.get('slot')

    # Free up previous slot if user is re-booking
    previous_booking = Schedule.query.filter_by(booked_by=ob_name).first()
    if previous_booking:
        previous_booking.booked_by = None

    # Book the new slot, checking for race conditions
    target_slot = Schedule.query.filter_by(slot=slot_to_book).first()
    if target_slot.booked_by is not None:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': '申し訳ありません、その時間は先ほど予約されました。'}), 409
    
    target_slot.booked_by = ob_name
    db.session.commit()

    return jsonify({'status': 'success', 'message': f'「{slot_to_book}」で予約を確定しました。'})

if __name__ == '__main__':
    # This block is for local development only.
    app.run(debug=True)
