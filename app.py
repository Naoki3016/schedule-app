import os
import base64
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import unquote
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_here') # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to login page if not authenticated

# --- Database Models ---
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot = db.Column(db.String(100), unique=True, nullable=False)
    booked_by = db.Column(db.String(100), nullable=True) # OB's name

# --- User Model for Flask-Login ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # In a real app, hash passwords!

    def __repr__(self):
        return '<User %r>' % self.username

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
@login_required # Requires login to access this page
def admin_page():
    with app.app_context():
        db.create_all() # Creates tables if they don't exist
        # Create a default admin user if not exists (for first run)
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='password') # CHANGE THIS PASSWORD!
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user 'admin' with password 'password' created.")

    data = get_app_data()
    return render_template('index.html', data=data, current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.password == password: # In real app: use werkzeug.security.check_password_hash
            login_user(user)
            flash('ログインしました。', 'success')
            return redirect(url_for('admin_page'))
        else:
            flash('ユーザー名またはパスワードが間違っています。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))

@app.route('/setup', methods=['POST'])
@login_required # Requires login to access this endpoint
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
    # This part is for local development only. Render will use gunicorn.
    with app.app_context():
        db.create_all()
        # Create a default admin user if not exists (for first run)
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='password') # CHANGE THIS PASSWORD!
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user 'admin' with password 'password' created.")
    app.run(debug=True)