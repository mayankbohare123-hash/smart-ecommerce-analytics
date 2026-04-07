@echo off
start cmd /k "D: && cd D:\project\smart-ecommerce-analytics\backend && uvicorn app.main:app --reload"
timeout /t 3
start cmd /k "D: && cd D:\project\smart-ecommerce-analytics\frontend && npm run dev"
timeout /t 3
start chrome http://localhost:5173