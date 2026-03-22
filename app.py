from flask import Flask, render_template_string, request, jsonify
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
from models import db, Prediction

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///predictions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

FEATURES = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach", "exang"]

FEATURE_DESCRIPTIONS = {
    "age": "Age",
    "sex": "Gender [0=Female, 1=Male]",
    "cp": "Chest Pain Type [0-3]",
    "trestbps": "Resting Blood Pressure (mmHg)",
    "chol": "Serum Cholesterol (mg/dl)",
    "fbs": "Fasting Blood Sugar [0=≤120, 1=>120]",
    "restecg": "Resting ECG Results [0,1,2]",
    "thalach": "Maximum Heart Rate Achieved",
    "exang": "Exercise Induced Angina [0=No, 1=Yes]"
}

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>Health Risk Prediction System</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .container-wrapper {
      width: 100%;
      max-width: 800px;
      padding: 20px;
    }
    .card {
      border: none;
      border-radius: 15px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
      overflow: hidden;
    }
    .card-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 30px;
      text-align: center;
      border: none;
    }
    .card-header h1 {
      margin: 0;
      font-size: 2.5rem;
      font-weight: 600;
    }
    .card-header p {
      margin: 10px 0 0 0;
      font-size: 1.1rem;
      opacity: 0.9;
    }
    .form-group {
      margin-bottom: 1.5rem;
    }
    .form-label {
      font-weight: 600;
      color: #333;
      margin-bottom: 0.5rem;
      display: block;
      font-size: 0.95rem;
    }
    .form-hint {
      font-size: 0.8rem;
      color: #666;
      margin-top: 3px;
      font-style: italic;
    }
    .form-control {
      border: 2px solid #e0e0e0;
      border-radius: 8px;
      padding: 10px 15px;
      font-size: 1rem;
      transition: all 0.3s ease;
    }
    .form-control:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
      outline: none;
    }
    .btn-predict {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      color: white;
      padding: 12px 30px;
      font-size: 1.1rem;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      width: 100%;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .btn-predict:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
      color: white;
    }
    .btn-predict:active {
      transform: translateY(0);
    }
    .result-box {
      margin-top: 30px;
      padding: 25px;
      border-radius: 12px;
      text-align: center;
      animation: slideUp 0.5s ease;
    }
    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    .result-low {
      background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
      color: #155724;
      border: 2px solid #28a745;
    }
    .result-medium {
      background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
      color: #856404;
      border: 2px solid #ffc107;
    }
    .result-high {
      background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
      color: #721c24;
      border: 2px solid #dc3545;
    }
    .result-title {
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 15px;
    }
    .result-prob {
      font-size: 1.3rem;
      font-weight: 500;
      opacity: 0.9;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
    }
    .card-body {
      padding: 30px;
    }
  </style>
</head>
<body>
  <div class="container-wrapper">
    <div class="card">
      <div class="card-header">
        <h1>❤️ Heart Disease Risk Prediction System</h1>
        <p>Enter health parameters to predict heart disease risk</p>
        <a href="/dashboard" target="_blank" style="color: white; text-decoration: underline; font-size: 0.9rem;">📊 View Statistics Dashboard</a>
      </div>
      <div class="card-body">
        <form method="post" action="/predict">
          <div class="form-grid">
            {% for feature in features %}
              <div class="form-group">
                <label class="form-label" for="{{ feature }}">{{ descriptions[feature] }}</label>
                <input type="number" class="form-control" id="{{ feature }}" name="{{ feature }}" step="0.01" required placeholder="Enter value">
              </div>
            {% endfor %}
          </div>
          <button type="submit" class="btn-predict">🔍 Predict</button>
        </form>

        {% if outcome %}
          {% if outcome == 'Low risk' %}
            <div class="result-box result-low">
              <div class="result-title">✅ {{ outcome }} (Low Risk)</div>
              <div class="result-prob">Probability: <strong>{{ (probability * 100)|round(2) }}%</strong></div>
              <p style="margin-top: 10px; font-size: 0.95rem;">Your health indicators show low risk of heart disease. 💪</p>
            </div>
          {% elif outcome == 'Medium risk' %}
            <div class="result-box result-medium">
              <div class="result-title">⚠️ {{ outcome }} (Medium Risk)</div>
              <div class="result-prob">Probability: <strong>{{ (probability * 100)|round(2) }}%</strong></div>
              <p style="margin-top: 10px; font-size: 0.95rem;">Please monitor your health closely and consult with a doctor. 👨‍⚕️</p>
            </div>
          {% else %}
            <div class="result-box result-high">
              <div class="result-title">🚨 {{ outcome }} (High Risk)</div>
              <div class="result-prob">Probability: <strong>{{ (probability * 100)|round(2) }}%</strong></div>
              <p style="margin-top: 10px; font-size: 0.95rem;">Please consult immediately with a healthcare professional. 🏥</p>
            </div>
          {% endif %}
        {% endif %}
      </div>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


def load_model(model_path="model/model.pkl"):
    try:
        return joblib.load(model_path)
    except Exception as ex:
        raise RuntimeError(f"Failed to load model from {model_path}: {ex}")


def risk_category(prob):
    if prob < 0.33:
        return "Low risk"
    if prob < 0.66:
        return "Medium risk"
    return "High risk"


@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML, features=FEATURES, descriptions=FEATURE_DESCRIPTIONS, outcome=None)


@app.route("/predict", methods=["POST"])
def predict():
    model = load_model()
    values = []
    feature_dict = {}
    try:
        for f in FEATURES:
            val = float(request.form[f])
            values.append(val)
            feature_dict[f] = val
    except Exception as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    x = np.array(values).reshape(1, -1)
    proba = model.predict_proba(x)[0][1]
    outcome = risk_category(proba)

    # Save to database
    pred = Prediction(
        age=feature_dict['age'],
        sex=feature_dict['sex'],
        cp=feature_dict['cp'],
        trestbps=feature_dict['trestbps'],
        chol=feature_dict['chol'],
        fbs=feature_dict['fbs'],
        restecg=feature_dict['restecg'],
        thalach=feature_dict['thalach'],
        exang=feature_dict['exang'],
        outcome=outcome,
        probability=round(float(proba), 4)
    )
    db.session.add(pred)
    db.session.commit()

    return render_template_string(
        HTML,
        features=FEATURES,
        descriptions=FEATURE_DESCRIPTIONS,
        outcome=outcome,
        probability=round(float(proba), 4),
    )


@app.route("/api/predict", methods=["POST"])
def api_predict():
    model = load_model()
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    values = []
    feature_dict = {}
    try:
        for f in FEATURES:
            if f not in data:
                return jsonify({"error": f"Missing feature: {f}"}), 400
            val = float(data[f])
            values.append(val)
            feature_dict[f] = val
    except ValueError as e:
        return jsonify({"error": f"Invalid value: {e}"}), 400
    
    x = np.array(values).reshape(1, -1)
    proba = model.predict_proba(x)[0][1]
    outcome = risk_category(proba)
    
    # Save to database
    pred = Prediction(
        age=feature_dict['age'],
        sex=feature_dict['sex'],
        cp=feature_dict['cp'],
        trestbps=feature_dict['trestbps'],
        chol=feature_dict['chol'],
        fbs=feature_dict['fbs'],
        restecg=feature_dict['restecg'],
        thalach=feature_dict['thalach'],
        exang=feature_dict['exang'],
        outcome=outcome,
        probability=round(float(proba), 4)
    )
    db.session.add(pred)
    db.session.commit()
    
    return jsonify({
        "outcome": outcome,
        "probability": round(float(proba), 4)
    })


@app.route("/dashboard", methods=["GET"])
def dashboard():
    predictions = Prediction.query.all()
    
    if not predictions:
        return f"<h1>📊 Dashboard</h1><p>No data available. Please make some predictions first to view statistics!</p><a href='/'>Back to Home</a>"
    
    # Convert to DataFrame
    data = [p.to_dict() for p in predictions]
    df = pd.DataFrame(data)
    
    # Create charts
    # 1. Risk distribution pie chart
    risk_counts = df['outcome'].value_counts()
    fig_risk = px.pie(
        values=risk_counts.values,
        names=risk_counts.index,
        title="📊 Risk Distribution",
        color_discrete_map={'Low risk': '#84fab0', 'Medium risk': '#fee140', 'High risk': '#ff6b6b'}
    )
    chart_risk = fig_risk.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 2. Age distribution histogram
    fig_age = px.histogram(
        df,
        x='age',
        nbins=10,
        title="📈 Age Distribution",
        labels={'age': 'Age', 'count': 'Count'}
    )
    chart_age = fig_age.to_html(full_html=False, include_plotlyjs=False)
    
    # 3. Average probability by outcome
    avg_prob = df.groupby('outcome')['probability'].mean().reset_index()
    fig_prob = px.bar(
        avg_prob,
        x='outcome',
        y='probability',
        title="⚖️ Average Probability by Risk Level",
        labels={'outcome': 'Risk Level', 'probability': 'Probability'}
    )
    chart_prob = fig_prob.to_html(full_html=False, include_plotlyjs=False)
    
    # 4. Max heart rate by outcome
    fig_hr = px.box(
        df,
        x='outcome',
        y='thalach',
        title="❤️ Max Heart Rate by Risk Level",
        labels={'outcome': 'Risk Level', 'thalach': 'Heart Rate'}
    )
    chart_hr = fig_hr.to_html(full_html=False, include_plotlyjs=False)
    
    # Statistics
    total_preds = len(df)
    low_risk_pct = (df['outcome'] == 'Low risk').sum() / total_preds * 100
    medium_risk_pct = (df['outcome'] == 'Medium risk').sum() / total_preds * 100
    high_risk_pct = (df['outcome'] == 'High risk').sum() / total_preds * 100
    avg_age = df['age'].mean()
    avg_chol = df['chol'].mean()
    
    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Dashboard - Health Risk Prediction</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .dashboard-container {{
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            }}
            .stat-box {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                margin-bottom: 20px;
            }}
            .stat-value {{
                font-size: 2rem;
                font-weight: bold;
            }}
            .stat-label {{
                font-size: 0.9rem;
                opacity: 0.9;
            }}
            h1 {{
                color: #667eea;
                text-align: center;
                margin-bottom: 30px;
            }}
            .chart-container {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
            }}
            .nav-buttons {{
                text-align: center;
                margin-bottom: 20px;
            }}
            .nav-buttons a {{
                margin: 0 10px;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="dashboard-container" style="max-width: 1200px; margin: 0 auto;">
            <div class="nav-buttons">
                <a href="/" class="btn btn-primary">🔙 Quay lại</a>
                <a href="/api/export" class="btn btn-success">📥 Export CSV</a>
            </div>
            
            <h1>📊 Statistics Dashboard</h1>
            
            <div class="row">
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-value">{total_preds}</div>
                        <div class="stat-label">Total Predictions</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-value">{low_risk_pct:.1f}%</div>
                        <div class="stat-label">Low Risk</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-value">{medium_risk_pct:.1f}%</div>
                        <div class="stat-label">Average Risk</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box">
                        <div class="stat-value">{high_risk_pct:.1f}%</div>
                        <div class="stat-label">High Risk</div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="chart-container">
                        {chart_risk}
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="chart-container">
                        {chart_age}
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="chart-container">
                        {chart_prob}
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="chart-container">
                        {chart_hr}
                    </div>
                </div>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <div class="col-md-12">
                    <div class="stat-box" style="margin-bottom: 0;">
                        <p>📈 Average Age: <strong>{avg_age:.1f}</strong> | Average Cholesterol: <strong>{avg_chol:.1f} mg/dl</strong></p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@app.route("/api/export", methods=["GET"])
def export_csv():
    predictions = Prediction.query.all()
    if not predictions:
        return jsonify({"error": "No data available"}), 400
    
    data = [p.to_dict() for p in predictions]
    df = pd.DataFrame(data)
    
    csv_data = df.to_csv(index=False)
    return csv_data, 200, {"Content-Disposition": "attachment; filename=predictions.csv"}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
