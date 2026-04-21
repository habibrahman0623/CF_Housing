import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from datetime import datetime, timezone
from typing import Optional
from fastapi.responses import FileResponse
from pathlib import Path # এটি পোর্টেবল পাথের জন্য জরুরি

router = APIRouter(prefix="/expenses", tags=["Expense Management"])

# ফোল্ডার তৈরি
EXPENSE_UPLOAD_DIR = "uploads/expenses"
os.makedirs(EXPENSE_UPLOAD_DIR, exist_ok=True)

@router.post("/add")
async def add_expense(
    amount: float = Form(...),
    description: str = Form(...),
    category: Optional[str] = Form(None),
    asset_id: Optional[int] = Form(None),
    voucher_no: Optional[str] = Form(None),
    payment_method: str = Form("Cash"),
    expense_date: Optional[datetime] = Form(None), # ফ্রন্টএন্ড থেকে ডেট পাঠালে সেটি নেওয়ার ব্যবস্থা
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    clean_path = None
    
    # যদি বিল বা রিসিটের ছবি আপলোড করা হয়
    if file:
        # ১. ফাইলের নাম ক্লিনআপ (স্পেস সরিয়ে আন্ডারস্কোর দেওয়া)
        safe_filename = file.filename.replace(" ", "_")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}"
        
        # ২. ওএস স্পেসিফিক পাথ (ফাইল রাইট করার জন্য)
        file_path = os.path.join(EXPENSE_UPLOAD_DIR, filename)
        
        # ৩. ডাটাবেসের জন্য পোজিক্স পাথ (forward slash)
        clean_path = Path(file_path).as_posix()
        
        # ফাইল সেভ করা (অরিজিনাল file_path ব্যবহার করে)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # ফাইনাল ডেট নির্ধারণ
    # ইউজার যদি নির্দিষ্ট ডেট পাঠায় তবে সেটি, নয়তো বর্তমান সময়
    final_date = expense_date if expense_date else datetime.now(timezone.utc)

    # ডাটাবেসে এন্ট্রি
    new_expense = models.Expense(
        category=category,
        asset_id=asset_id,
        amount=amount,
        description=description,
        voucher_no=voucher_no,
        payment_method=payment_method,
        document_path=clean_path, # এখানে / স্ল্যাশ ওয়ালা পাথ যাচ্ছে
        expense_date=final_date
    )
    
    try:
        db.add(new_expense)
        db.commit()
        db.refresh(new_expense)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    return {
        "status": "Success",
        "expense_id": new_expense.id,
        "message": "Expense recorded successfully",
        "file_path": clean_path
    }

from sqlalchemy.orm import joinedload

@router.get("/list")
def list_expenses(db: Session = Depends(get_db)):
    # joinedload ব্যবহার করলে expenses-এর সাথে asset-এর তথ্যও একবারে চলে আসবে
    expenses = db.query(models.Expense).options(joinedload(models.Expense.asset)).order_by(models.Expense.expense_date.desc()).all()
    
    result = []
    for exp in expenses:
        result.append({
            "id": exp.id,
            "category": exp.category,
            "amount": exp.amount,
            "expense_date": exp.expense_date,
            "description": exp.description,
            "voucher_no": exp.voucher_no,
            "payment_method": exp.payment_method,
            "document_path": exp.document_path,
            "asset_id": exp.asset_id,
            # যদি অ্যাসেট থাকে তবে নাম যাবে, না থাকলে None
            "asset_name": exp.asset.name if exp.asset else None 
        })
    return result


@router.get("/download-document/{expense_id}")
def download_asset_document(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    
    if not expense or not expense.document_path:
        raise HTTPException(status_code=404, detail="Document not found for this asset")
    
    return FileResponse(expense.document_path)