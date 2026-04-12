import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from datetime import datetime, timezone, date
from typing import List, Optional
import json

router = APIRouter(prefix="/external-loans", tags=["Liability & Loans"])

# ফাইল সেভ করার ডিরেক্টরি
LOAN_DOC_DIR = "uploads/loan_documents"
os.makedirs(LOAN_DOC_DIR, exist_ok=True)

@router.post("/add-loan")
async def add_external_loan(
    lender_name: str = Form(...),
    principal: float = Form(...),
    total_interest: float = Form(...),
    issued_date: date = Form(...),
    # কিস্তিগুলো স্ট্রিং হিসেবে আসবে, পরে আমরা এটাকে লিস্টে রূপান্তর করব
    installments_json: str = Form(...), 
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    file_path = None
    if file:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(LOAN_DOC_DIR, f"loan_{timestamp}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # লোন মাস্টার রেকর্ড তৈরি
    new_loan = models.ExternalLoan(
        lender_name=lender_name,
        principal_amount=principal,
        total_interest_amount=total_interest,
        total_payable=principal + total_interest,
        remaining_balance=principal + total_interest,
        issued_date=issued_date,
        document_path=file_path, 
        status="Active"
    )
    db.add(new_loan)
    db.commit()
    db.refresh(new_loan)

    # কিস্তির JSON ডেটা প্রসেস করা
    installments = json.loads(installments_json)
    for ins in installments:
        schedule = models.ExternalLoanSchedule(
            loan_id=new_loan.id,
            due_date=ins['due_date'],
            principal_component=ins['principal_amount'],
            interest_component=ins['interest_amount'],
            total_installment=ins['principal_amount'] + ins['interest_amount'],
            status="Pending"
        )
        db.add(schedule)
    
    db.commit()
    return {"message": "Loan, Document and Schedule created successfully", "loan_id": new_loan.id}

from datetime import datetime, timezone
from typing import Optional

@router.post("/repay-installment/{schedule_id}")
def repay_loan_installment(
    schedule_id: int, 
    amount_paid: float, 
    payment_date: Optional[datetime] = None, # এডমিন থেকে ইনপুট
    db: Session = Depends(get_db)
):
    schedule = db.query(models.ExternalLoanSchedule).filter(
        models.ExternalLoanSchedule.id == schedule_id
    ).first()

    if not schedule or schedule.status == "Paid":
        raise HTTPException(status_code=400, detail="কিস্তিটি পাওয়া যায়নি বা ইতিমধ্যে পরিশোধিত।")

    loan = db.query(models.ExternalLoan).filter(models.ExternalLoan.id == schedule.loan_id).first()

    # ১. পেমেন্ট তারিখ নির্ধারণ
    # যদি এডমিন তারিখ পাঠায় তবে সেটি ব্যবহার হবে, নাহলে বর্তমান সময়
    if payment_date:
        schedule.payment_date = payment_date
    else:
        schedule.payment_date = datetime.now(timezone.utc)

    # ২. ব্যালেন্স আপডেট
    schedule.paid_amount += amount_paid
    loan.remaining_balance -= amount_paid

    # ৩. স্ট্যাটাস চেক
    if schedule.paid_amount >= schedule.total_installment:
        schedule.status = "Paid"
    else:
        schedule.status = "Partial"

    # ৪. লোন ক্লোজ করার লজিক
    remaining_schedules = db.query(models.ExternalLoanSchedule).filter(
        models.ExternalLoanSchedule.loan_id == loan.id,
        models.ExternalLoanSchedule.status != "Paid"
    ).count()

    if remaining_schedules == 0 and loan.remaining_balance <= 0:
        loan.status = "Closed"

    db.commit()
    return {
        "message": "Loan Payment Successfull", 
        "applied_payment_date": schedule.payment_date,
        "new_status": schedule.status
    }

@router.get("/summary/{loan_id}")
def get_loan_summary(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(models.ExternalLoan).filter(models.ExternalLoan.id == loan_id).first()
    schedules = db.query(models.ExternalLoanSchedule).filter(
        models.ExternalLoanSchedule.loan_id == loan_id
    ).all()

    return {
        "loan_info": loan,
        "installments": schedules
    }

from sqlalchemy.orm import joinedload

@router.get("/pending-installments")
def list_pending_installments(db: Session = Depends(get_db)):
    # ১. ExternalLoanSchedule এবং ExternalLoan জয়েন করা হচ্ছে লেন্ডারের নাম পাওয়ার জন্য
    # ২. ফিল্টার করা হচ্ছে শুধুমাত্র 'Pending' এবং 'Partial' স্ট্যাটাসগুলো
    # ৩. সাজানো হচ্ছে due_date অনুযায়ী (Ascending - আগে যেটা দিতে হবে সেটা আগে)
    
    pending_list = db.query(models.ExternalLoanSchedule)\
        .join(models.ExternalLoan)\
        .filter(models.ExternalLoanSchedule.status.in_(["Pending", "Partial"]))\
        .order_by(models.ExternalLoanSchedule.due_date.asc())\
        .all()

    result = []
    for item in pending_list:
        # লোন মাস্টার টেবিল থেকে লেন্ডারের নাম নেওয়া
        lender_name = db.query(models.ExternalLoan.lender_name)\
            .filter(models.ExternalLoan.id == item.loan_id).scalar()
            
        result.append({
            "schedule_id": item.id,
            "lender_name": lender_name,
            "due_date": item.due_date,
            "installment_amount": item.total_installment,
            "paid_so_far": item.paid_amount,
            "remaining_to_pay": item.total_installment - item.paid_amount,
            "status": item.status
        })

    return result