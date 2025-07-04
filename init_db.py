import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import db, User, Config, Schedule # Import models and db from app.py

# Create a minimal Flask app context for database operations
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Tables created.")

    # Create a default admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='password') # CHANGE THIS PASSWORD IN PRODUCTION!
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user 'admin' with password 'password' created.")
    else:
        print("Admin user already exists.")
