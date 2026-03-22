from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Prediction(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Float, nullable=False)
    sex = db.Column(db.Float, nullable=False)
    cp = db.Column(db.Float, nullable=False)
    trestbps = db.Column(db.Float, nullable=False)
    chol = db.Column(db.Float, nullable=False)
    fbs = db.Column(db.Float, nullable=False)
    restecg = db.Column(db.Float, nullable=False)
    thalach = db.Column(db.Float, nullable=False)
    exang = db.Column(db.Float, nullable=False)
    
    outcome = db.Column(db.String(20), nullable=False)  # Low risk, Medium risk, High risk
    probability = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'age': self.age,
            'sex': self.sex,
            'cp': self.cp,
            'trestbps': self.trestbps,
            'chol': self.chol,
            'fbs': self.fbs,
            'restecg': self.restecg,
            'thalach': self.thalach,
            'exang': self.exang,
            'outcome': self.outcome,
            'probability': self.probability,
            'created_at': self.created_at.isoformat()
        }
