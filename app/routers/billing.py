from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/billing", tags=["Billing & Dues"])



@router.post("/generate-monthly-contribution")
def generate_monthly_contribution(request: schemas.MonthlyBillRequest, db: Session = Depends(get_db)):
    active_members = db.query(models.Member).filter(models.Member.status == "Active").all()
    
    # এই মাস ও বছরের জন্য আগে থেকেই যাদের বিল আছে তাদের আইডি সংগ্রহ করা
    existing_member_ids = [
        row[0] for row in db.query(models.MonthlyBill.member_id).filter(
            models.MonthlyBill.billing_period == request.billing_period
        ).all()
    ]

    new_bills = []
    y, m = map(int, request.billing_period.split("-"))
    due_dt = request.due_date or datetime(y, m, 15, 23, 59)
    for member in active_members:
        # যদি এই মেম্বারের বিল আগে থেকে না থাকে (Single বা অন্যভাবে), তবেই লিস্টে যোগ করো
        if member.id not in existing_member_ids:
            amount = member.share_count * request.rate_per_share
            new_bills.append(models.MonthlyBill(
                member_id=member.id,
                billing_period=request.billing_period,
                amount=amount,
                due_date=due_dt,
                is_paid=False
            ))
    
    if not new_bills:
        return {"message": "All active members already have bills for this period. No new bills created."}

    db.add_all(new_bills)
    db.commit()
    return {"message": f"Successfully generated bills for {len(new_bills)} members. (Skipped: {len(existing_member_ids)})"}



@router.delete("/cancel-monthly-bill/{bill_id}")
def cancel_monthly_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(models.MonthlyBill).filter(models.MonthlyBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    # নিরাপত্তা চেক: বিল যদি অলরেডি পেইড হয়ে যায়, তবে ডিলিট করা যাবে না
    if bill.is_paid:
        raise HTTPException(status_code=400, detail="Cannot cancel a bill that is already paid!")

    db.delete(bill)
    db.commit()
    return {"message": "Bill has been successfully cancelled and removed."}


# --- ২. স্মার্ট স্পেশাল চার্জ জেনারেটর (Bulk) ---
@router.post("/generate-special-charge")
def generate_special_charge(request: schemas.SpecialChargeRequest, db: Session = Depends(get_db)):
    active_members = db.query(models.Member).filter(models.Member.status == "Active").all()
    
    # ওই নির্দিষ্ট বিলের নামে ইতিমধ্যে যাদের বিল জেনারেট হয়েছে তাদের আইডি সংগ্রহ
    existing_member_ids = [
        row[0] for row in db.query(models.SpecialBill.member_id).filter(
            models.SpecialBill.bill_name == request.bill_name
        ).all()
    ]

    new_charges = []
    for member in active_members:
        # যদি এই মেম্বারের এই বিলটি আগে না থেকে থাকে
        if member.id not in existing_member_ids:
            final_amount = member.share_count * request.amount if request.is_per_share else request.amount
            
            new_charges.append(models.SpecialBill(
                member_id=member.id,
                bill_name=request.bill_name,
                description=request.description,
                amount=final_amount,
                due_date=request.due_date,
                is_paid=False
            ))
    
    if not new_charges:
        return {"message": "All active members already have this special bill. No new entries created."}

    db.add_all(new_charges)
    db.commit()
    return {"message": f"Successfully applied '{request.bill_name}' to {len(new_charges)} members. (Skipped: {len(existing_member_ids)})"}


@router.delete("/cancel-special-bill/{bill_id}")
def cancel_special_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(models.SpecialBill).filter(models.SpecialBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Special Bill not found")
    
    # পেইড হয়ে গেলে ডিলিট করা রিস্কি, তাই চেক বসানো ভালো
    if bill.is_paid:
        raise HTTPException(status_code=400, detail="Cannot cancel a bill that has already been paid!")

    db.delete(bill)
    db.commit()
    return {"message": f"Special bill '{bill.bill_name}' has been successfully cancelled."}


# ১. Single Monthly Bill
@router.post("/generate-single-monthly/{member_id}")
def generate_single_monthly_bill(
    member_id: int, 
    request: schemas.MonthlyBillRequest, 
    db: Session = Depends(get_db)
):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # ডুপ্লিকেট চেক: একই মাস ও বছরে এই মেম্বারের মান্থলি বিল আছে কি না

    existing = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.member_id == member_id,
        models.MonthlyBill.billing_period == request.billing_period
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Monthly bill already exists for this period")

    # ডিফল্ট ১৫ তারিখ সেট করা যদি ইউজার না দেয়
    y, m = map(int, request.billing_period.split("-"))
    due_dt = request.due_date or datetime(y, m, 15, 23, 59)
    new_bill = models.MonthlyBill(
      member_id=member.id,
            billing_period=request.billing_period,
            amount=member.share_count * request.rate_per_share,
            due_date=due_dt,
            is_paid=False
    )
    db.add(new_bill)
    db.commit()
    return {"message": f"Monthly bill generated for {member.name}", "amount": new_bill.amount}

# ২. Single Special/Fixed Charge
@router.post("/generate-single-special/{member_id}")
def generate_single_special_charge(
    member_id: int, 
    request: schemas.SpecialChargeRequest, 
    db: Session = Depends(get_db)
):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    #description = f"Monthly Contribution: {request.month}/{request.year}"
    existing = db.query(models.SpecialBill).filter(
        models.SpecialBill.member_id == member_id,
        models.SpecialBill.bill_name == request.bill_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Special bill already exists for this person")
    # লজিক: মেম্বারের শেয়ার অনুযায়ী নাকি সরাসরি ফিক্সড অ্যামাউন্ট?
    final_amount = request.amount
    if request.is_per_share:
        final_amount = member.share_count * request.amount

    new_charge = models.SpecialBill(
        member_id=member.id,
        bill_name=request.bill_name,
        description=request.description,
        amount=final_amount,
        due_date=request.due_date,
        is_paid=False
    )
    db.add(new_charge)
    db.commit()
    return {"message": f"Special charge '{request.description}' generated for {member.name}"}

# --- মান্থলি বিল ফিল্টারসহ দেখার API ---
@router.get("/monthly-bills", response_model=list[schemas.MonthlyBillResponse])
def get_monthly_bills(
    billing_period: Optional[str] = None, 
    status: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(models.MonthlyBill)
    if billing_period:
        query = query.filter(models.MonthlyBill.billing_period == billing_period)
    if status:
        query = query.filter(models.MonthlyBill.status == status)    
    
    return query.all()

# --- স্পেশাল বিল ফিল্টারসহ দেখার API ---
@router.get("/special-bills", response_model=list[schemas.SpecialBillResponse])
def get_special_bills(
    bill_name: Optional[str] = None,
    status: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(models.SpecialBill)
    if bill_name:
        query = query.filter(models.SpecialBill.bill_name.ilike(f"%{bill_name}%"))
    if status:
        query = query.filter(models.SpecialBill.status == status)    
    
    return query.all()

# মান্থলি বিলের জন্য বাল্ক জরিমানা (ডাবল প্রিভেনশনসহ)
@router.post("/apply-bulk-fine-monthly")
def apply_bulk_fine_monthly(billing_period: str, fine_amount: float, db: Session = Depends(get_db)):
    # শুধুমাত্র সেই বিলগুলো ফিল্টার করা হচ্ছে যেগুলোর ওপর এখনো জরিমানা ধার্য হয়নি
    bills_to_fine = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.billing_period == billing_period,
        models.MonthlyBill.status != "Paid",
        models.MonthlyBill.is_fined == False  # ডাবল জরিমানা প্রতিরোধ
    ).all()

    if not bills_to_fine:
        return {"message": "No new eligible bills found for fining in this period (Already fined or paid)."}

    for bill in bills_to_fine:
        bill.is_fined = True
        bill.fine_amount = fine_amount
        bill.member.total_fine_charged += fine_amount

    db.commit()
    return {"message": f"Success: Fine of {fine_amount} applied to {len(bills_to_fine)} members."}

# @router.post("/waive-fine-monthly")
# def waive_fine_monthly(member_code: str, billing_period: str, db: Session = Depends(get_db)):
#     # ১. মেম্বার কোড দিয়ে মেম্বার খুঁজে বের করা
#     member = db.query(models.Member).filter(models.Member.member_code == member_code).first()
#     if not member:
#         raise HTTPException(status_code=404, detail="Member not found.")

#     # ২. ওই মেম্বারের নির্দিষ্ট মাসের বিলটি খুঁজে বের করা
#     bill = db.query(models.MonthlyBill).filter(
#         models.MonthlyBill.member_id == member.id,
#         models.MonthlyBill.billing_period == billing_period
#     ).first()

#     if not bill:
#         raise HTTPException(status_code=404, detail=f"No bill found for {billing_period}.")

#     if not bill.is_fined or bill.fine_amount <= bill.fine_paid_amount:
#         raise HTTPException(status_code=400, detail="No unpaid fine exists for this month.")

#     # ৩. জরিমানা মওকুফ লজিক
#     unpaid_fine = bill.fine_amount - bill.fine_paid_amount
#     member.total_fine_charged -= unpaid_fine # মেম্বারের টোটাল চার্জ থেকে কমিয়ে দেওয়া
    
#     # বিলের জরিমানা রিসেট (যা অলরেডি পেইড শুধু সেটুকুই থাকবে)
#     bill.fine_amount = bill.fine_paid_amount 
#     bill.is_fined = False if bill.fine_amount == 0 else True

#     db.commit()
#     return {
#         "message": f"Success: {unpaid_fine} TK fine waived for {member.name} ({billing_period}).",
#         "new_fine_amount": bill.fine_amount
#     }

@router.post("/waive-fine-monthly")
def waive_fine_monthly(request: schemas.WaiverRequest, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.member_code == request.member_code).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    bill = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.member_id == member.id,
        models.MonthlyBill.billing_period == request.billing_period
    ).first()

    if not bill or not bill.is_fined or bill.fine_amount <= bill.fine_paid_amount:
        raise HTTPException(status_code=400, detail="No unpaid fine found for this month.")

    # অডিট ট্রেইল এবং মওকুফ লজিক
    unpaid_fine = bill.fine_amount - bill.fine_paid_amount
    member.total_fine_charged -= unpaid_fine 
    
    bill.fine_amount = bill.fine_paid_amount 
    bill.is_fined = False if bill.fine_amount == 0 else True
    bill.fine_waive_reason = request.reason # কারণ সেভ হচ্ছে
    bill.fine_waived_at = datetime.now()     # সময় সেভ হচ্ছে

    db.commit()
    return {"message": f"Fine of {unpaid_fine} waived for {member.name}. Reason: {request.reason}"}

@router.post("/apply-bulk-fine-special")
def apply_bulk_fine_special(bill_name: str, fine_amount: float, db: Session = Depends(get_db)):
    """
    বিলের নাম (যেমন: 'Picnic 2026') ইনপুট দিলে ওই বিলের বিপরীতে যারা টাকা দেয়নি তাদের জরিমানা হবে।
    """
    unpaid_special_bills = db.query(models.SpecialBill).filter(
        models.SpecialBill.bill_name == bill_name,
        models.SpecialBill.status != "Paid",
        models.SpecialBill.is_fined == False
    ).all()

    if not unpaid_special_bills:
        raise HTTPException(status_code=404, detail="No unpaid special bills found with this name.")

    for s_bill in unpaid_special_bills:
        s_bill.is_fined = True
        s_bill.fine_amount += fine_amount
        s_bill.member.total_fine_charged += fine_amount

    db.commit()
    return {"message": f"Fine applied to {len(unpaid_special_bills)} members for bill: {bill_name}."}


# @router.post("/waive-fine-special")
# def waive_fine_special(member_code: str, bill_name: str, db: Session = Depends(get_db)):
#     # ১. মেম্বার কোড দিয়ে মেম্বার খুঁজে বের করা
#     member = db.query(models.Member).filter(models.Member.member_code == member_code).first()
#     if not member:
#         raise HTTPException(status_code=404, detail="Member not found.")

#     # ২. নির্দিষ্ট স্পেশাল বিলটি খুঁজে বের করা
#     s_bill = db.query(models.SpecialBill).filter(
#         models.SpecialBill.member_id == member.id,
#         models.SpecialBill.bill_name == bill_name
#     ).first()

#     if not s_bill:
#         raise HTTPException(status_code=404, detail=f"Special bill '{bill_name}' not found.")

#     if not s_bill.is_fined or s_bill.fine_amount <= s_bill.fine_paid_amount:
#         raise HTTPException(status_code=400, detail="No unpaid fine exists for this special bill.")

#     # ৩. জরিমানা মওকুফ লজিক
#     unpaid_fine = s_bill.fine_amount - s_bill.fine_paid_amount
#     member.total_fine_charged -= unpaid_fine
    
#     s_bill.fine_amount = s_bill.fine_paid_amount
#     s_bill.is_fined = False if s_bill.fine_amount == 0 else True

#     db.commit()
#     return {"message": f"Special fine '{bill_name}' waived for {member.name}."}


@router.post("/waive-fine-special")
def waive_fine_special(request: schemas.WaiverRequest, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.member_code == request.member_code).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    s_bill = db.query(models.SpecialBill).filter(
        models.SpecialBill.member_id == member.id,
        models.SpecialBill.bill_name == request.bill_name
    ).first()

    if not s_bill or not s_bill.is_fined or s_bill.fine_amount <= s_bill.fine_paid_amount:
        raise HTTPException(status_code=400, detail="No unpaid fine found for this special bill.")

    unpaid_fine = s_bill.fine_amount - s_bill.fine_paid_amount
    member.total_fine_charged -= unpaid_fine
    
    s_bill.fine_amount = s_bill.fine_paid_amount
    s_bill.is_fined = False if s_bill.fine_amount == 0 else True
    s_bill.fine_waive_reason = request.reason
    s_bill.fine_waived_at = datetime.now()

    db.commit()
    return {"message": f"Special fine '{request.bill_name}' waived successfully."}