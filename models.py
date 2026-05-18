from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    university = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship("Result", backref="user", lazy=True)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    case_id = db.Column(db.String(50), nullable=False)
    case_label = db.Column(db.String(100), nullable=False)
    checklist_score = db.Column(db.Integer, default=0)
    checklist_possible = db.Column(db.Integer, default=0)
    viva_score = db.Column(db.Integer, default=0)
    viva_possible = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)
    total_possible = db.Column(db.Integer, default=0)
    global_impression = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)