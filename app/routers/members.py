from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from typing import List

router = APIRouter(prefix="/members", tags=["Members"])


@router.post("/", response_model=schemas.MemberResponse)
def create_member(member: schemas.MemberCreate, db: Session = Depends(get_db)):
    
    db_member = db.query(models.Member).filter(models.Member.member_code == member.member_code).first()
    if db_member:
        raise HTTPException(status_code=400, detail="Member Code already exists")
    
    new_member = models.Member(**member.model_dump())
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member


@router.get("/", response_model=List[schemas.MemberResponse])
def get_all_members(db: Session = Depends(get_db)):
    return db.query(models.Member).all()


@router.get("/members-info")
def get_members_info(db: Session = Depends(get_db)):
    # ১. সকল মেম্বার এবং তাদের বিলগুলো সংগ্রহ করা
    members = db.query(models.Member).filter(models.Member.status == "Active").all()
    
    members_info = []

    for member in members:
        # মান্থলি বিলের বকেয়া হিসাব
        monthly_bills = db.query(models.MonthlyBill).filter(models.MonthlyBill.member_id == member.id).all()
        m_principal_due = sum(b.amount - b.paid_amount for b in monthly_bills)
        m_fine_due = sum(b.fine_amount - b.fine_paid_amount for b in monthly_bills)

        # স্পেশাল বিলের বকেয়া হিসাব
        special_bills = db.query(models.SpecialBill).filter(models.SpecialBill.member_id == member.id).all()
        s_principal_due = sum(sb.amount - sb.paid_amount for sb in special_bills)
        s_fine_due = sum(sb.fine_amount - sb.fine_paid_amount for sb in special_bills)

        # টোটাল বকেয়া
        total_due = m_principal_due + m_fine_due + s_principal_due + s_fine_due

        
        members_info.append({
            "id":member.id,
            "name": member.name,
            "member_code": member.member_code,
            "share_count": member.share_count,
            "advance_balance": member.advance_balance,
            "phone":member.phone,
            "email": member.email,
            "nid": member.nid,
            "address": member.address,
            "status": member.status,
            "total_fine_charged": member.total_fine_charged,
            "total_fine_paid": member.total_fine_paid,
            "total_due": total_due
        })

    # ৩. বকেয়া অনুযায়ী বড় থেকে ছোট ক্রমানুসারে সাজানো (যাদের বকেয়া বেশি তারা আগে আসবে)
    members_info = sorted(members_info, key=lambda x: x["total_due"], reverse=True)

    return {
        "total_members": len(members_info),
        "data": members_info
    }

@router.get("/dropdown-list")
def get_member_dropdown(db: Session = Depends(get_db)):
    # শুধু ID, Name এবং Member_Code সিলেক্ট করা হচ্ছে
    members = db.query(models.Member.id, models.Member.name, models.Member.member_code).filter(models.Member.status == "Active").all()
    
    # ড্রপডাউনের সুবিধার্থে একটি লিস্ট তৈরি করা
    return [{"id": m.id, "display_name": f"{m.name} ({m.member_code})", "code": m.member_code} for m in members]


@router.get("/{member_code}", response_model=schemas.MemberResponse)
def get_single_member(member_code: str, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.member_code == member_code).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.get("/member-statement/{member_code}")
def get_member_statement(member_code: str, db: Session = Depends(get_db)):
    # ১. মেম্বার খুঁজে বের করা
    member = db.query(models.Member).filter(models.Member.member_code == member_code).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # ২. সকল মান্থলি বিল সংগ্রহ করা
    monthly_bills = db.query(models.MonthlyBill).filter(models.MonthlyBill.member_id == member.id).all()
    
    # ৩. সকল স্পেশাল বিল সংগ্রহ করা
    special_bills = db.query(models.SpecialBill).filter(models.SpecialBill.member_id == member.id).all()
    
    # ৪. সকল পেমেন্ট হিস্ট্রি (মানি রিসিট) সংগ্রহ করা
    payment_history = db.query(models.Payment).filter(models.Payment.member_id == member.id).order_by(models.Payment.payment_date.desc()).all()

    # ৫. মোট হিসাব ক্যালকুলেট করা (সামারি)
    total_bill = sum(b.amount for b in monthly_bills) + sum(sb.amount for sb in special_bills)
    total_fine = member.total_fine_charged
    total_paid = sum(p.amount_received for p in payment_history)

    return {
        "member_info": {
            "name": member.name,
            "code": member.member_code,
            "advance_balance": member.advance_balance
        },
        "summary": {
            "total_bill_charged": total_bill,
            "total_fine_charged": total_fine,
            "total_paid": total_paid,
            "current_due": (total_bill + total_fine) - (total_paid + member.advance_balance)
        },
        "monthly_bills": monthly_bills,
        "special_bills": special_bills,
        "payment_history": payment_history
    }
