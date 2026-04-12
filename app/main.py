from fastapi import FastAPI
import app.models as models
from app.database import engine
from app.routers import assets, members, billing, payments, reports, expenses, external_loans, auth
from fastapi.middleware.cors import CORSMiddleware

print("Main file loaded 🚀")

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(members.router)
app.include_router(billing.router)
app.include_router(payments.router)
app.include_router(reports.router)
app.include_router(assets.router)
app.include_router(expenses.router)
app.include_router(external_loans.router)
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins= [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
], # আপনার ফ্রন্টএন্ডের ইউআরএল
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to CF Housing Cooperative API 🚀", "status": "Online"}