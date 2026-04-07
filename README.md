# SalesIQ — Smart E-Commerce Analytics Platform

> Upload CSV sales data → get instant analytics, interactive charts, and ML-powered 30-day revenue forecasts.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-1.5-orange)

---

## Features

- **CSV Upload** — Drag-and-drop upload with automatic column detection and data validation
- **KPI Dashboard** — Revenue, orders, AOV, unique customers, top product, top region, MoM growth
- **Interactive Charts** — Monthly trend, top products bar, category doughnut, regional breakdown
- **ML Predictions** — 30-day revenue forecast using Random Forest with confidence intervals
- **REST API** — Fully documented, Postman-testable FastAPI backend
- **Production Ready** — Docker, Gunicorn, error handling, tests

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn / Gunicorn |
| Data | Pandas + NumPy |
| ML | Scikit-learn (Random Forest + Linear Regression) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | React 18 + Vite |
| Charts | Chart.js + react-chartjs-2 |
| Styling | Tailwind CSS |
| Testing | Pytest + httpx |
| Deployment | Render / Railway / Docker |

---

## Project Structure

```
smart-ecommerce-analytics/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── database.py          # SQLAlchemy models
│   │   ├── routes/              # upload, analytics, visualize, predict
│   │   ├── services/            # upload, analytics, visualization, prediction
│   │   ├── models/schemas.py    # Pydantic response types
│   │   ├── ml/                  # train.py, predict.py
│   │   └── utils/               # validators, file helpers
│   ├── tests/                   # 50+ pytest tests
│   ├── uploads/                 # uploaded CSV files
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/          # Sidebar, KPICards, Charts, FileUpload
│   │   ├── pages/               # Dashboard, Upload, Analytics, Predictions
│   │   ├── services/            # api.js, analyticsApi.js, predictApi.js
│   │   └── context/             # DataContext (global state)
│   ├── Dockerfile
│   └── package.json
├── data/
│   └── sample_sales.csv         # 2,790-row demo dataset
├── docker-compose.yml
└── README.md
```

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 20+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/smart-ecommerce-analytics.git
cd smart-ecommerce-analytics
```

### 2. Backend setup
```bash
cd backend
cp .env.example .env        # edit .env if needed
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at **http://localhost:8000**
Swagger docs at **http://localhost:8000/docs**

### 3. Frontend setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

### 4. Try it out
1. Open http://localhost:5173
2. Go to **Upload Data** and drag-and-drop `data/sample_sales.csv`
3. Dashboard auto-loads with KPIs and charts
4. Go to **Predictions** to run the ML forecast (first run ~5 seconds)

---

## Docker (Full Stack)

```bash
cp backend/.env.example backend/.env
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

## API Reference

All endpoints are prefixed with `/api`. Full interactive docs at `/docs`.

### Upload
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload a CSV file |
| `GET` | `/api/upload/files` | List all uploads |
| `GET` | `/api/upload/files/{id}` | File metadata |
| `GET` | `/api/upload/preview/{id}` | Preview rows |
| `GET` | `/api/upload/validate/{id}` | Column mapping |
| `DELETE` | `/api/upload/files/{id}` | Delete file |

### Analytics
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analytics/{id}` | Full analytics payload |
| `GET` | `/api/analytics/{id}/kpis` | KPI metrics |
| `GET` | `/api/analytics/{id}/monthly` | Monthly time series |
| `GET` | `/api/analytics/{id}/products` | Top products |
| `GET` | `/api/analytics/{id}/regions` | Regional breakdown |

### Visualizations
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/visualize/{id}` | All chart data |
| `GET` | `/api/visualize/{id}/trend` | Revenue line chart |
| `GET` | `/api/visualize/{id}/products` | Products bar chart |
| `GET` | `/api/visualize/{id}/category` | Category doughnut |
| `GET` | `/api/visualize/{id}/regions` | Region bar chart |

### Predictions
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/predict/{id}` | 30-day forecast |
| `POST` | `/api/predict/{id}/retrain` | Force re-training |
| `GET` | `/api/predict/{id}/metrics` | Model metrics |
| `GET` | `/api/predict/{id}/chart` | Forecast chart data |

---

## Sample Dataset

`data/sample_sales.csv` — 2,790 rows of realistic e-commerce sales data:
- **Period**: Jan 2023 – Mar 2024 (15 months)
- **Products**: 20 items across 8 categories
- **Regions**: North, South, East, West, Central
- **Features**: order_id, order_date, customer_id, product, category, region, quantity, unit_price, total_price, discount, net_revenue, payment_method
- **Seasonality**: Nov–Dec holiday peaks, summer uplift

---

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

Test coverage:
- `tests/test_upload.py`    — 14 tests (upload validation, file management)
- `tests/test_analytics.py` — 22 tests (KPI math, sorting, HTTP endpoints)
- `tests/test_visualize.py` — 23 tests (chart structure, Chart.js compatibility)
- `tests/test_predict.py`   — 20 tests (feature engineering, ML training, forecasting)

---

## Deployment

### Render (recommended free tier)

**Backend:**
1. New Web Service → connect your GitHub repo
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
5. Add environment variables:
   ```
   APP_ENV=production
   SECRET_KEY=<generate a strong key>
   DATABASE_URL=<your PostgreSQL URL from Render>
   CORS_ORIGINS=https://your-frontend.onrender.com
   ```

**Frontend:**
1. New Static Site → connect your GitHub repo
2. Root directory: `frontend`
3. Build command: `npm install && npm run build`
4. Publish directory: `dist`
5. Add env var: `VITE_API_URL=https://your-backend.onrender.com/api`

**PostgreSQL:**
1. New PostgreSQL → free tier
2. Copy the Internal Connection URL into backend's `DATABASE_URL`

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Deploy backend
cd backend
railway init
railway up

# Deploy frontend
cd ../frontend
railway init
railway up
```

Set the same environment variables as Render above.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | (dev key) | Secret for signing — **change in production** |
| `DATABASE_URL` | `sqlite:///./ecommerce.db` | SQLite or PostgreSQL URL |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded CSV files |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload size in MB |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `PREDICTION_DAYS` | `30` | How many days to forecast |

---

## CSV Format Guide

Your CSV must contain at minimum:

| Column | Accepted names | Required |
|---|---|---|
| Date | `order_date`, `date`, `sale_date` | ✅ |
| Revenue | `net_revenue`, `revenue`, `total`, `sales` | ✅ |
| Product | `product`, `product_name`, `item` | Optional |
| Category | `category`, `product_category` | Optional |
| Region | `region`, `area`, `zone`, `territory` | Optional |
| Quantity | `quantity`, `qty`, `units_sold` | Optional |
| Customer | `customer_id`, `user_id` | Optional |

---

## License

MIT — free to use, modify, and distribute.

---

*Built with FastAPI, React, Pandas, and Scikit-learn.*
