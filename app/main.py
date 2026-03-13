from fastapi import FastAPI
import app.models as models
from app.database import engine
from app.routers import assets, members, billing, payments, reports, expenses, external_loans

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

@app.get("/")
def read_root():
    return {"message": "Welcome to CF Housing Cooperative API 🚀", "status": "Online"}