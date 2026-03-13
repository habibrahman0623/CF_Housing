import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/expenses", tags=["Expense Management"])

# খরচের ডকুমেন্টের জন্য আলাদা ফোল্ডার
EXPENSE_UPLOAD_DIR = "uploads/expenses"
os.makedirs(EXPENSE_UPLOAD_DIR, exist_ok=True)

@router.post("/add")
async def add_expense(
    category_id: int = Form(...),
    amount: float = Form(...),
    description: str = Form(...),
    asset_id: Optional[int] = Form(None),
    voucher_no: Optional[str] = Form(None),
    payment_method: str = Form("Cash"),
    file: Optional[UploadFile] = File(None), # রিসিট বা ভাউচার ফাইল
    db: Session = Depends(get_db)
):
    file_path = None
    
    # যদি বিল বা রিসিটের ছবি আপলোড করা হয়
    if file:
        # ফাইলের নাম ইউনিক করার জন্য টাইমস্ট্যাম্প যোগ করা
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(EXPENSE_UPLOAD_DIR, f"{timestamp}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # ডাটাবেসে এন্ট্রি (datetime.now(timezone.utc) ব্যবহার করে)
    new_expense = models.Expense(
        category_id=category_id,
        asset_id=asset_id,
        amount=amount,
        description=description,
        voucher_no=voucher_no,
        payment_method=payment_method,
        document_path=file_path, # মডেলে এই কলামটি থাকতে হবে
        expense_date=datetime.now(timezone.utc)
    )
    
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    
    return {
        "status": "Success",
        "expense_id": new_expense.id,
        "message": "Expense recorded with document successfully"
    }