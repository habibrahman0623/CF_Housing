from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from datetime import datetime

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/collect")
def collect_payment(request: schemas.CollectPayment, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == request.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # মোট এভেলেবল টাকা = আজকের ক্যাশ + আগের জমানো অ্যাডভান্স
    total_available = request.cash_received + member.advance_balance
    
    # বকেয়া বিলগুলো সংগ্রহ করা (পুরানো বিল আগে আসবে - FIFO)
    unpaid_monthly = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.member_id == request.member_id, 
        models.MonthlyBill.status != "Paid"
    ).order_by(models.MonthlyBill.billing_period).all()

    unpaid_special = db.query(models.SpecialBill).filter(
        models.SpecialBill.member_id == request.member_id, 
        models.SpecialBill.status != "Paid"
    ).all()

    # --- ১. মান্থলি বিলের জরিমানা আগে অ্যাডজাস্ট করা ---
    for bill in unpaid_monthly:
        due_fine = bill.fine_amount - bill.fine_paid_amount
        if due_fine > 0:
            if total_available >= due_fine:
                total_available -= due_fine
                bill.fine_paid_amount += due_fine
                member.total_fine_paid += due_fine
            else:
                bill.fine_paid_amount += total_available
                member.total_fine_paid += total_available
                total_available = 0
                break
    
    # --- ২. স্পেশাল বিলের জরিমানা অ্যাডজাস্ট করা ---
    if total_available > 0:
        for s_bill in unpaid_special:
            due_fine = s_bill.fine_amount - s_bill.fine_paid_amount
            if due_fine > 0:
                if total_available >= due_fine:
                    total_available -= due_fine
                    s_bill.fine_paid_amount += due_fine
                    member.total_fine_paid += due_fine
                else:
                    s_bill.fine_paid_amount += total_available
                    member.total_fine_paid += total_available
                    total_available = 0
                    break

    # --- ৩. মান্থলি বিলের মূল টাকা (Principal) অ্যাডজাস্ট করা ---
    if total_available > 0:
        for bill in unpaid_monthly:
            due_principal = bill.amount - bill.paid_amount
            if due_principal > 0:
                if total_available >= due_principal:
                    total_available -= due_principal
                    bill.paid_amount += due_principal
                    bill.status = "Paid"
                    bill.is_paid = True
                else:
                    bill.paid_amount += total_available
                    bill.status = "Partial"
                    total_available = 0
                    break

    # --- ৪. স্পেশাল বিলের মূল টাকা (Principal) অ্যাডজাস্ট করা ---
    if total_available > 0:
        for s_bill in unpaid_special:
            due_principal = s_bill.amount - s_bill.paid_amount
            if due_principal > 0:
                if total_available >= due_principal:
                    total_available -= due_principal
                    s_bill.paid_amount += due_principal
                    s_bill.status = "Paid"
                    s_bill.is_paid = True
                else:
                    s_bill.paid_amount += total_available
                    s_bill.status = "Partial"
                    total_available = 0
                    break

    # সবশেষে যা বাঁচবে তা অ্যাডভান্স ব্যালেন্সে জমা হবে
    member.advance_balance = total_available
    
    # ট্রানজাকশন সেভ করা (মানি রিসিট হিস্ট্রির জন্য)
    new_payment = models.Payment(
        member_id = request.member_id,
        amount_received = request.cash_received,
        payment_date=datetime.now(),
        receipt_no = f"MR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    )
    db.add(new_payment)
    
    db.commit()
    return {
        "message": "Payment collected and bills adjusted",
        "member_code": member.member_code,
        "member_name": member.name,
        "payment_amount": new_payment.amount_received,
        "new_advance_balance": total_available,
        "receipt_no": new_payment.receipt_no
    }

@router.get("/payment-receipt/{receipt_no}")
def get_payment_receipt(receipt_no: str, db: Session = Depends(get_db)):
    # রিসিট নাম্বার দিয়ে পেমেন্ট রেকর্ড খুঁজে বের করা
    payment = db.query(models.Payment).filter(models.Payment.receipt_no == receipt_no).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Receipt not found")

    member = payment.member

    return {
        "receipt_no": payment.receipt_no,
        "date": payment.payment_date,
        "member_name": member.name,
        "member_code": member.member_code,
        "amount_received": payment.amount_received,
        "payment_method": payment.payment_method,
        "note": payment.note,
        "current_advance": member.advance_balance,
        "footer_msg": "Thank you for your contribution!"
    }