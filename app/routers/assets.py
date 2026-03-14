import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from datetime import date
from typing import Optional

router = APIRouter(prefix="/assets", tags=["Asset Management"])

# ফাইল সেভ করার ফোল্ডার তৈরি
UPLOAD_DIR = "uploads/assets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/add")
async def add_asset(
    name: str = Form(...),
    category: str = Form(...),
    amount: float = Form(...),
    purchase_date: date = Form(...),
    funding_source: str = Form("General Fund"),
    depreciation_method: str = Form("None"),
    useful_life_years: int = Form(0),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None), # ফাইলটি অপশনাল রাখা হয়েছে
    db: Session = Depends(get_db)
):
    file_path = None
    
    # যদি ইউজার ফাইল আপলোড করে
    if file:
        file_path = os.path.join(UPLOAD_DIR, f"{date.today()}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # ডাটাবেসে এন্ট্রি
    new_asset = models.Asset(
        name=name,
        category=category,
        purchase_amount=amount,
        purchase_date=purchase_date,
        funding_source=funding_source,
        depreciation_method=depreciation_method,
        useful_life_years=useful_life_years,
        description=description,
        document_path=file_path,
        current_book_value=amount
    )
    
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    
    return {
        "status": "Success",
        "message": "Asset and document saved successfully",
        "asset_id": new_asset.id,
        "file_stored_at": file_path
    }

from fastapi.responses import FileResponse

@router.get("/download-document/{asset_id}")
def download_asset_document(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    
    if not asset or not asset.document_path:
        raise HTTPException(status_code=404, detail="Document not found for this asset")
    
    return FileResponse(asset.document_path)

@router.get("/list")
def list_assets(db: Session = Depends(get_db)):
    # শুধুমাত্র সচল অ্যাসেটগুলোর তালিকা
    assets = db.query(models.Asset).filter(models.Asset.is_disposed == False).all()
    
    result = []
    for asset in assets:
        result.append({
            "id": asset.id,
            "name": asset.name,
            "category": asset.category,
            "purchase_amount": asset.purchase_amount,
            "purchase_date": asset.purchase_date,
            "current_book_value": asset.current_book_value,
            "has_document": True if asset.document_path else False, # ফ্রন্টএন্ডে আইকন দেখানোর জন্য
            "funding_source": asset.funding_source
        })
    
    return result

from datetime import date

@router.post("/run-depreciation")
def run_depreciation(db: Session = Depends(get_db)):
    # ১. শুধুমাত্র সেই অ্যাসেটগুলো নিন যেগুলোর অবচয় পদ্ধতি "Straight-Line" এবং যেগুলো এখনো বিক্রি হয়নি
    assets = db.query(models.Asset).filter(
        models.Asset.depreciation_method == "Straight-Line",
        models.Asset.is_disposed == False,
        models.Asset.current_book_value > models.Asset.salvage_value
    ).all()

    updates_count = 0
    total_depreciation_amt = 0.0

    for asset in assets:
        if asset.useful_life_years > 0:
            # ২. বার্ষিক অবচয় সূত্র: (ক্রয়মূল্য - স্ক্র্যাপ ভ্যালু) / মোট বছর
            annual_depreciation = (asset.purchase_amount - asset.salvage_value) / asset.useful_life_years
            
            # ৩. নতুন বুক ভ্যালু ক্যালকুলেট করা
            new_value = asset.current_book_value - annual_depreciation
            
            # নিশ্চিত করা যেন স্ক্র্যাপ ভ্যালুর নিচে না নামে
            if new_value < asset.salvage_value:
                annual_depreciation = asset.current_book_value - asset.salvage_value
                new_value = asset.salvage_value

            # ৪. আপডেট করা
            asset.current_book_value = new_value
            total_depreciation_amt += annual_depreciation
            updates_count += 1

    db.commit()
    
    return {
        "status": "Success",
        "assets_updated": updates_count,
        "total_depreciation_value": total_depreciation_amt,
        "message": f"Depreciation run completed for {updates_count} assets."
    }    

@router.post("/record-income")
async def record_asset_income(
    asset_id: int = Form(...),
    amount: float = Form(...),
    income_type: str = Form(...), # Rent/Sale/Scrap
    description: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # সম্পদটি আছে কি না চেক করা
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # ফাইল সেভ করার লজিক (আগের মতো)
    file_path = None
    if file:
        # সেভ করার কোড এখানে...
        pass

    new_income = models.AssetIncome(
        asset_id=asset_id,
        amount=amount,
        income_type=income_type,
        description=description,
        document_path=file_path
    )
    
    # যদি সম্পদটি বিক্রি (Sale) করা হয়, তবে অ্যাসেট স্ট্যাটাস আপডেট করা
    if income_type.lower() == "sale":
        asset.is_disposed = True
        asset.disposal_date = date.today()
        asset.disposal_amount = amount

    db.add(new_income)
    db.commit()
    return {"message": "Asset income recorded successfully"}