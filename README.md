uvicorn backend.app.main:app --reload --port 8000



📊 Agri Price Forecast

Quantile ML-based Forecasting System for Agri-Horticultural Commodities

A full-stack forecasting system that predicts probabilistic price ranges (q10, q50, q90) for agri-horticultural commodities across Indian states and markets.

Built using:

⚙ FastAPI (Backend API)

🧠 Quantile Machine Learning Models (LightGBM / XGBoost / SARIMAX / GRU experiments)

🎨 React (Vite) + TailwindCSS (Frontend UI)

📦 LocalStorage history + JSON export

🔍 Fallback-aware feature engineering logic

---

🚀 Features

📈 Probabilistic Forecasting

q10 → Low estimate

q50 → Median estimate

q90 → High estimate

Interval width for uncertainty estimation


🧠 Intelligent Fallback Logic

If exact historical match is not found, system automatically falls back to:

Latest in series

State + commodity

Commodity only

Date-only (low confidence)


Confidence badge is shown in UI.

📊 Insights Panel

Predicted range

Spread (uncertainty width)

Confidence level

Interpretation note


🕘 Prediction History

Last 5 predictions saved locally

Reload past results instantly

Clear history option


📥 JSON Export

Download prediction results as structured JSON.


---

🏗 Project Structure

agri-price-forecast/
│
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/          # Routes
│   │   ├── services/     # Feature builder, model loader
│   │   └── main.py
│   └── requirements.txt
│
├── frontend/             # React (Vite + Tailwind)
│   └── src/
│
├── ml/                   # ML pipeline (EDA, training, evaluation)
│
├── docker-compose.yml
├── README.md
└── .gitignore


---

🛠 Local Setup Guide

1️⃣ Clone Repository

git clone https://github.com/Chandana0048/agri-price-forecast.git
cd agri-price-forecast


---

2️⃣ Backend Setup (FastAPI)

cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000

Backend will run at:

http://127.0.0.1:8000

Health check:

http://127.0.0.1:8000/health


---

3️⃣ Frontend Setup (React)

Open a new terminal:

cd frontend
npm install
npm run dev

Frontend runs at:

http://127.0.0.1:5173
----

🔌 API Endpoints

Health Check

GET /health

Meta Data

GET /meta/states
GET /meta/commodities
GET /meta/markets?state=Karnataka
GET /meta/top-markets?state=Karnataka&commodity=Onion&k=5

Prediction

POST /predict

Request body:

{
  "state": "Karnataka",
  "market": "Bangalore APMC",
  "commodity": "Onion",
  "arrival_date": "2026-02-10"
}

Response:

{
  "q10": 3100.25,
  "q50": 3400.50,
  "q90": 3800.80,
  "interval_width": 700.55,
  "fallback_level": "exact"
}


---

🧠 Modeling Approach

Time-series feature engineering

Lag features & rolling averages

Seasonal encoding

Weather aggregation

Market arrival normalization

Quantile regression models (LightGBM)

Experimental models: SARIMAX, GRU, XGBoost

Model comparison pipeline



---

🛡 Best Practices Implemented

Modular architecture

Clean separation of API & services

Fallback-aware feature construction

.gitignore for clean repository

Docker-ready structure

CI workflow

Branch-based collaboration



---




---

📄 License

MIT License


---

👩‍💻 Author

Chandana
AI & Data Science Undergraduate
Quantile ML Forecasting Project


---

🌟 Future Improvements

Model versioning (MLflow)

Deployment (Render / Railway / AWS)

Authentication layer

Advanced uncertainty calibration

Real-time market ingestion



---
