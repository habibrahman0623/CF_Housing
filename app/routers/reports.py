from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from app.database import get_db
from app import models
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import date, datetime, time, timezone

router = APIRouter(prefix="/reports", tags=["Reports & Dashboard"])

@router.get("/dashboard-summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    now = datetime.now()
    today = now.date()
    current_month = now.month
    current_year = now.year

    # ১. মেম্বার পরিসংখ্যান
    active_members = db.query(models.Member).filter(models.Member.status == "Active").count()
    
    # ২. বকেয়া হিসাব (Monthly + Special)
    m_stats = db.query(
        func.sum(models.MonthlyBill.amount - models.MonthlyBill.paid_amount).label("p_due"),
        func.sum(models.MonthlyBill.fine_amount - models.MonthlyBill.fine_paid_amount).label("f_due")
    ).first()

    s_stats = db.query(
        func.sum(models.SpecialBill.amount - models.SpecialBill.paid_amount).label("p_due"),
        func.sum(models.SpecialBill.fine_amount - models.SpecialBill.fine_paid_amount).label("f_due")
    ).first()

    # ৩. কালেকশন পরিসংখ্যান (আজ, এই মাস, এই বছর)
    # আজকের কালেকশন
    today_col = db.query(func.sum(models.Payment.amount_received)).filter(
        func.date(models.Payment.payment_date) == today
    ).scalar() or 0.0

    # এই মাসের কালেকশন
    month_col = db.query(func.sum(models.Payment.amount_received)).filter(
        func.extract('month', models.Payment.payment_date) == current_month,
        func.extract('year', models.Payment.payment_date) == current_year
    ).scalar() or 0.0

    # এই বছরের কালেকশন
    year_col = db.query(func.sum(models.Payment.amount_received)).filter(
        func.extract('year', models.Payment.payment_date) == current_year
    ).scalar() or 0.0

    #সর্বমোট কালেকশন 
    total_collection = db.query(func.sum(models.Payment.amount_received)).scalar() or 0.0

    # মোট অ্যাডভান্স ব্যালেন্স যা সমিতির কাছে জমা আছে
    total_advance = db.query(func.sum(models.Member.advance_balance)).scalar() or 0.0

    # বকেয়া যোগফল
    grand_due = (m_stats.p_due or 0) + (m_stats.f_due or 0) + (s_stats.p_due or 0) + (s_stats.f_due or 0)

    return {
        "member_stats": {
            "active_members": active_members
        },
        "collection_summary": {
            "today": today_col,
            "this_month": month_col,
            "this_year": year_col,
            "total_collection": total_collection,
            "total_advance_held": total_advance
        },
        "due_summary": {
            "total_outstanding": grand_due,
            "monthly_bill_due": (m_stats.p_due or 0),
            "special_bill_due": (s_stats.p_due or 0),
            "fine_due": (m_stats.f_due or 0) + (s_stats.f_due or 0)
        }
    }



@router.get("/collection-history")
def get_collection_history(
    start_date: Optional[date] = Query(None), 
    end_date: Optional[date] = Query(None), 
    db: Session = Depends(get_db)
):
    # যদি তারিখ না দেওয়া হয়, তবে আজকের তারিখ সেট হবে
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = date.today()

    # তারিখগুলোকে পূর্ণাঙ্গ সময়সহ (Start of day to End of day) কনভার্ট করা
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    # ট্রানজাকশন কুয়েরি
    transactions = db.query(models.Payment).filter(
        models.Payment.payment_date >= start_datetime,
        models.Payment.payment_date <= end_datetime
    ).order_by(models.Payment.payment_date.desc()).all()

    # নির্দিষ্ট সময়ের মোট কালেকশন সামারি
    total_amount = sum(t.amount_received for t in transactions)

    # ডাটা ফরম্যাট করা (অ্যাপে দেখানোর সুবিধার জন্য)
    report_data = []
    for t in transactions:
        report_data.append({
            "receipt_no": t.receipt_no,
            "date": t.payment_date.strftime("%Y-%m-%d %I:%M %p"),
            "member_name": t.member.name,
            "member_code": t.member.member_code,
            "amount": t.amount_received,
            "method": t.payment_method,
            "note": t.note
        })

    return {
        "report_info": {
            "period": f"{start_date} to {end_date}",
            "total_transactions": len(transactions),
            "total_collected": total_amount
        },
        "data": report_data
    }

@router.get("/defaulter-list")
def get_defaulter_list(db: Session = Depends(get_db)):
    # ১. সকল মেম্বার এবং তাদের বিলগুলো সংগ্রহ করা
    members = db.query(models.Member).filter(models.Member.status == "Active").all()
    
    defaulters = []

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

        # ২. শুধুমাত্র যাদের বকেয়া আছে তাদের লিস্টে যোগ করা
        if total_due > 0:
            defaulters.append({
                "Name": member.name,
                "Member Code": member.member_code,
                "Monthly Due": m_principal_due,
                "Monthly Fine Due": m_fine_due,
                "Special Due": s_principal_due,
                "Special Fine Due": s_fine_due,
                "Total Due": total_due
            })

    # ৩. বকেয়া অনুযায়ী বড় থেকে ছোট ক্রমানুসারে সাজানো (যাদের বকেয়া বেশি তারা আগে আসবে)
    defaulters = sorted(defaulters, key=lambda x: x["Total Due"], reverse=True)

    return {
        "total_defaulters": len(defaulters),
        "total_outstanding_amount": sum(d["Total Due"] for d in defaulters),
        "data": defaulters
    }

@router.get("/defaulter-list-by-month")
def get_defaulter_list_by_month(billing_period: str, db: Session = Depends(get_db)):
    # ওই নির্দিষ্ট মাসের বিলগুলো ফিল্টার করা হচ্ছে যেগুলোর স্ট্যাটাস পেইড নয়
    unpaid_bills = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.billing_period == billing_period,
        models.MonthlyBill.status != "Paid"
    ).all()

    report_data = []
    for bill in unpaid_bills:
        principal_due = bill.amount - bill.paid_amount
        fine_due = bill.fine_amount - bill.fine_paid_amount
        
        report_data.append({
            "Name": bill.member.name,
            "Member Code": bill.member.member_code,
            "MOnthly Due": principal_due,
            "MOnthly Fine Due": fine_due,
            "Total Due": principal_due + fine_due
        })

    return {
        "period": billing_period,
        "total_unpaid_members": len(report_data),
        "data": report_data
    }

@router.get("/defaulter-list-by-special-bill")
def get_defaulter_list_by_special_bill(bill_name: str, db: Session = Depends(get_db)):
    # ওই নির্দিষ্ট নামের স্পেশাল বিলগুলো ফিল্টার করা
    unpaid_special_bills = db.query(models.SpecialBill).filter(
        models.SpecialBill.bill_name == bill_name,
        models.SpecialBill.status != "Paid"
    ).all()

    report_data = []
    for s_bill in unpaid_special_bills:
        principal_due = s_bill.amount - s_bill.paid_amount
        fine_due = s_bill.fine_amount - s_bill.fine_paid_amount
        
        report_data.append({
            "Name": s_bill.member.name,
            "Member Code": s_bill.member.member_code,
            "Special Bill Due": principal_due,
            "Special Bill Fine Due": fine_due,
            "Total Due": principal_due + fine_due
        })

    return {
        "bill_name": bill_name,
        "total_unpaid_members": len(report_data),
        "data": report_data
    }

@router.get("/all-monthly-summary")
def get_all_monthly_summary(db: Session = Depends(get_db)):
    # মাস অনুযায়ী গ্রুপ করে সামারি বের করা
    summaries = db.query(
        models.MonthlyBill.billing_period,
        func.sum(models.MonthlyBill.amount).label("total_principal"),
        func.sum(models.MonthlyBill.paid_amount).label("principal_collected"),
        func.sum(models.MonthlyBill.fine_amount).label("total_fine"),
        func.sum(models.MonthlyBill.fine_paid_amount).label("fine_collected")
    ).group_by(models.MonthlyBill.billing_period).order_by(models.MonthlyBill.billing_period.desc()).all()

    result = []
    for s in summaries:
        total_bill = s.total_principal + s.total_fine
        total_collected = s.principal_collected + s.fine_collected
        
        result.append({
            "Month": s.billing_period,
            "Total Principal Bill": s.total_principal,
            "Total Principal Bill Collection": s.principal_collected,
            "Total Fine Exposed": s.total_fine,
            "Total Fine Collection": s.fine_collected,
            "Total Bill": total_bill,
            "Total Collection": total_collected,
            "Performance": f"{(total_collected / total_bill * 100):.2f}%" if total_bill > 0 else "0%"
        })
    
    return result

@router.get("/all-special-summary")
def get_all_special_summary(db: Session = Depends(get_db)):
    # বিলের নাম অনুযায়ী গ্রুপ করা
    summaries = db.query(
        models.SpecialBill.bill_name,
        func.sum(models.SpecialBill.amount).label("total_principal"),
        func.sum(models.SpecialBill.paid_amount).label("principal_collected"),
        func.sum(models.SpecialBill.fine_amount).label("total_fine"),
        func.sum(models.SpecialBill.fine_paid_amount).label("fine_collected")
    ).group_by(models.SpecialBill.bill_name).all()

    # যেহেতু বিলের নাম স্ট্রিং, তাই আমরা আইডি বা ডেট দিয়ে শর্ট করার জন্য নিচের লিস্টটি ব্যবহার করতে পারি
    result = []
    for s in summaries:
        total_bill = s.total_principal + s.total_fine
        total_collected = s.principal_collected + s.fine_collected
        
        result.append({
            "Special Bill Name": s.bill_name,
            "Total Principal Bill": s.total_principal,
            "Total Principal Bill Collection": s.principal_collected,
            "Total Fine Exposed": s.total_fine,
            "Total Fine Collection": s.fine_collected,
            "Total Bill": total_bill,
            "Total Collection": total_collected,
            "Performance": f"{(total_collected / total_bill * 100):.2f}%" if total_bill > 0 else "0%"
        })

    # লেটেস্টগুলো উপরে রাখার জন্য ডিকশনারি লিস্টটি রিভার্স করা যেতে পারে
    return result[::-1]

@router.get("/monthly-collection-summary")
def get_monthly_collection_summary(billing_period: str, db: Session = Depends(get_db)):
    bills = db.query(models.MonthlyBill).filter(
        models.MonthlyBill.billing_period == billing_period
    ).all()

    if not bills:
        raise HTTPException(status_code=404, detail="No data found for this period.")

    total_principal_bill = sum(b.amount for b in bills)
    total_principal_collection = sum(b.paid_amount for b in bills)
    total_fine_exposed = sum(b.fine_amount for b in bills)
    total_fine_collection = sum(b.fine_paid_amount for b in bills)

    return {
        "Month": billing_period,
        "Total Principal Bill": total_principal_bill,
        "Total Principal Bill Collection": total_principal_collection,
        "Total Fine Exposed": total_fine_exposed,
        "Total Fine Collection": total_fine_collection,
        "Total Bill": total_principal_bill + total_fine_exposed,
        "Total Collection": total_principal_collection + total_fine_collection,
        "Collection Percentage": f"{(total_principal_collection + total_fine_collection) / (total_principal_bill + total_fine_exposed) * 100:.2f}%" if (total_principal_bill + total_fine_exposed) > 0 else "0%"
    }

@router.get("/special-collection-summary")
def get_special_collection_summary(bill_name: str, db: Session = Depends(get_db)):
    s_bills = db.query(models.SpecialBill).filter(
        models.SpecialBill.bill_name == bill_name
    ).all()

    if not s_bills:
        raise HTTPException(status_code=404, detail="No special bill found with this name.")

    total_principal_bill = sum(sb.amount for sb in s_bills)
    total_principal_collection = sum(sb.paid_amount for sb in s_bills)
    total_fine_exposed = sum(sb.fine_amount for sb in s_bills)
    total_fine_collection = sum(sb.fine_paid_amount for sb in s_bills)

    return {
        "Special Bill Name": bill_name,
        "Total Principal Bill": total_principal_bill,
        "Total Principal Bill Collection": total_principal_collection,
        "Total Fine Exposed": total_fine_exposed,
        "Total Fine Collection": total_fine_collection,
        "Total Bill": total_principal_bill + total_fine_exposed,
        "Total Collection": total_principal_collection + total_fine_collection,
        "Success Rate": f"{(total_principal_collection + total_fine_collection) / (total_principal_bill + total_fine_exposed) * 100:.2f}%" if (total_principal_bill + total_fine_exposed) > 0 else "0%"
    }


from app.dependencies import get_current_user

@router.get("/cash-in-hand")
def get_cash_in_hand_summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    current_year = datetime.now(timezone.utc).year

    # --- হেল্পার ফাংশন: ফিল্টারসহ সামারি বের করার জন্য ---
    def get_sums(model, amount_col, date_col, filter_year=None):
        query = db.query(func.sum(amount_col))
        if filter_year:
            query = query.filter(extract('year', date_col) == filter_year)
        return query.scalar() or 0

    # ==========================
    # CASH IN (আয় ও আমদানী)
    # ==========================
    
    # ১. মাসিক বিল ও জরিমানা
    m_all = get_sums(models.MonthlyBill, models.MonthlyBill.paid_amount + models.MonthlyBill.fine_paid_amount, models.MonthlyBill.payment_date)
    m_year = get_sums(models.MonthlyBill, models.MonthlyBill.paid_amount + models.MonthlyBill.fine_paid_amount, models.MonthlyBill.payment_date, current_year)
    
    # ২. স্পেশাল বিল ও জরিমানা (নতুন যুক্ত)
    s_all = get_sums(models.SpecialBill, models.SpecialBill.paid_amount + models.SpecialBill.fine_paid_amount, models.SpecialBill.payment_date)
    s_year = get_sums(models.SpecialBill, models.SpecialBill.paid_amount + models.SpecialBill.fine_paid_amount, models.SpecialBill.payment_date, current_year)

    # ৩. সম্পদ থেকে আয়
    a_inc_all = get_sums(models.AssetIncome, models.AssetIncome.amount, models.AssetIncome.income_date)
    a_inc_year = get_sums(models.AssetIncome, models.AssetIncome.amount, models.AssetIncome.income_date, current_year)

    # ৪. লোন নেওয়া (Principal Amount)
    loan_all = get_sums(models.ExternalLoan, models.ExternalLoan.principal_amount, models.ExternalLoan.issued_date)
    loan_year = get_sums(models.ExternalLoan, models.ExternalLoan.principal_amount, models.ExternalLoan.issued_date, current_year)

    # ==========================
    # CASH OUT (ব্যয় ও বিনিয়োগ)
    # ==========================
    
    # ১. সাধারণ খরচ (Expenses)
    exp_all = get_sums(models.Expense, models.Expense.amount, models.Expense.expense_date)
    exp_year = get_sums(models.Expense, models.Expense.amount, models.Expense.expense_date, current_year)

    # ২. সম্পদ কেনা (Asset Purchase - Funding Source: General Fund)
    # যেহেতু সম্পদে created_at ফিল্ড আছে, সেটি দিয়ে বছর ফিল্টার করছি
    asset_buy_all = db.query(func.sum(models.Asset.purchase_amount)).filter(models.Asset.funding_source == "General Fund").scalar() or 0
    asset_buy_year = db.query(func.sum(models.Asset.purchase_amount)).filter(
        models.Asset.funding_source == "General Fund",
        extract('year', models.Asset.purchase_date) == current_year # purchase_date অনুযায়ী ফিল্টার
    ).scalar() or 0

    # ৩. লোনের কিস্তি পরিশোধ (কিস্তির টাকা পরিশোধের সময় ক্যাশ আউট হয়)
    repay_all = get_sums(models.ExternalLoanSchedule, models.ExternalLoanSchedule.paid_amount, models.ExternalLoanSchedule.payment_date)
    repay_year = get_sums(models.ExternalLoanSchedule, models.ExternalLoanSchedule.paid_amount, models.ExternalLoanSchedule.payment_date, current_year)

    # ==========================
    # চূড়ান্ত ক্যালকুলেশন
    # ==========================
    
    total_in_all = m_all + s_all + a_inc_all + loan_all
    total_in_year = m_year + s_year + a_inc_year + loan_year
    
    total_out_all = exp_all + asset_buy_all + repay_all
    total_out_year = exp_year + asset_buy_year + repay_year

    return {
        "current_year": current_year,
        "lifetime_summary": {
            "total_cash_in": total_in_all,
            "total_cash_out": total_out_all,
            "net_fund_available": total_in_all - total_out_all
        },
        "this_year_summary": {
            "total_cash_in": total_in_year,
            "total_cash_out": total_out_year,
            "net_surplus_deficit": total_in_year - total_out_year
        },
        "details_this_year": {
            "income": {
                "monthly_bills": m_year,
                "special_bills": s_year,
                "asset_income": a_inc_year,
                "loans_received": loan_year
            },
            "expense": {
                "general_expenses": exp_year,
                "asset_investments": asset_buy_year,
                "loan_repayments": repay_year
            }
        }
    }