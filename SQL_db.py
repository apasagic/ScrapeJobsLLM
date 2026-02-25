from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    link = db.Column(db.String)
    description = db.Column(db.Text)
    experience = db.Column(db.String)
    skills = db.Column(db.String)
    tags = db.Column(db.String)
    salary = db.Column(db.String)
    location = db.Column(db.String)
    source = db.Column(db.String)
    job_fitness = db.Column(db.String)
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    cv_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
