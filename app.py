import json
import base64
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DATA_FILE = 'data.json'

def read_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'ob_names': [], 'time_slots': [], 'schedule': {}}

def write_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/')
def admin_page():
    data = read_data()
    return render_template('index.html', data=data)

@app.route('/setup', methods=['POST'])
def setup_schedule():
    req_data = request.json
    ob_names = req_data.get('ob_names', [])
    time_slots = req_data.get('time_slots', [])

    new_schedule = {slot: None for slot in time_slots}

    data = {
        'ob_names': ob_names,
        'time_slots': time_slots,
        'schedule': new_schedule
    }
    write_data(data)
    return jsonify({'status': 'success', 'message': 'スケジュールが設定されました。'})

@app.route('/booking')
def booking_page():
    ob_id = request.args.get('ob')
    if not ob_id:
        return "エラー: 招待リンクが無効です。", 400
    
    try:
        ob_name = base64.b64decode(ob_id).decode('utf-8')
    except Exception:
        return "エラー: 招待リンクの形式が正しくありません。", 400

    data = read_data()
    if ob_name not in data.get('ob_names', []):
        return "エラー: あなたは招待されていません。", 403

    return render_template('booking.html', ob_name=ob_name, schedule=data['schedule'])

@app.route('/book', methods=['POST'])
def book_slot():
    req_data = request.json
    ob_name = req_data.get('ob_name')
    slot = req_data.get('slot')

    data = read_data()

    # Double-check for race conditions
    if data['schedule'].get(slot) is not None:
        return jsonify({'status': 'error', 'message': '申し訳ありません、その時間は先ほど予約されました。'}), 409

    # Free up previous slot if user is re-booking
    for s, name in data['schedule'].items():
        if name == ob_name:
            data['schedule'][s] = None

    data['schedule'][slot] = ob_name
    write_data(data)

    return jsonify({'status': 'success', 'message': f'「{slot}」で予約を確定しました。'})

@app.route('/status')
def schedule_status():
    return jsonify(read_data())

if __name__ == '__main__':
    app.run(debug=True)
