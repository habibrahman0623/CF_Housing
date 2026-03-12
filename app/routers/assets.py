from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from datetime import date

router = APIRouter(prefix="/assets", tags=["Asset Management"])

@router.post("/add")
def add_asset(name: str, category: str, amount: float, purchase_date: date, 
              method: str = "None", life: int = 0, db: Session = Depends(get_db)):
    
    # নতুন অ্যাসেট এন্ট্রি
    new_asset = models.Asset(
        name=name,
        category=category,
        purchase_amount=amount,
        purchase_date=purchase_date,
        depreciation_method=method,
        useful_life_years=life,
        current_book_value=amount, # শুরুতে বুক ভ্যালু ক্রয়মূল্যের সমান
        funding_source="General Fund" # ডিফল্ট
    )
    
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    return {"message": "Asset added successfully", "asset_id": new_asset.id}

@router.get("/list")
def list_assets(db: Session = Depends(get_db)):
    # শুধুমাত্র সচল অ্যাসেটগুলোর তালিকা (Disposed গুলো বাদ দিয়ে)
    assets = db.query(models.Asset).filter(models.Asset.is_disposed == False).all()
    return assets

