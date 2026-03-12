from sqlalchemy import Column, Integer,Text, DateTime, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    member_code = Column(String, unique=True, index=True) 
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
   
    address = Column(Text, nullable=True)
    nid = Column(String, unique=True, nullable=True) 
    
    share_count = Column(Integer, default=1)
    advance_balance = Column(Float, default=0.0)
    total_fine_charged = Column(Float, default=0.0) # মোট জরিমানা কত হয়েছে
    total_fine_paid = Column(Float, default=0.0)    # মেম্বার কত জরিমানা দিয়েছে
    status = Column(String, default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class MonthlyBill(Base):
    __tablename__ = "monthly_bills"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"))
    # month = Column(Integer) # ১ থেকে ১২
    # year = Column(Integer)  # যেমন: ২০২৬
    billing_period = Column(String)
    amount = Column(Float)  # (Share Count * Rate)
    paid_amount = Column(Float, default=0.0) # মেম্বার কত টাকা মূল বিলের বিপরীতে দিয়েছে
    
    is_fined = Column(Boolean, default=False) # জরিমানা আছে কি না
    fine_amount = Column(Float, default=0.0)  # জরিমানার পরিমাণ
    fine_paid_amount = Column(Float, default=0.0) # জরিমানা কত টাকা পরিশোধ হয়েছে

    is_fined_waived = Column(Boolean, default=False)
    fine_waive_reason = Column(String, nullable=True) # কেন মওকুফ করা হলো
    fine_waived_at = Column(DateTime, nullable=True) # কখন মওকুফ করা হলো
    due_date = Column(DateTime) # এই তারিখের পর জরিমানা শুরু হবে
    is_paid = Column(Boolean, default=False)
    status = Column(String, default="Unpaid") # Unpaid, Partial, Paid

    member = relationship("Member")


# models.py এর MonthlyDue টেবিলটি এখন হবে 'Bill' বা 'Charge' টেবিল
class SpecialBill(Base):
    __tablename__ = "special_bills"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"))
    bill_name = Column(String) # 
    description = Column(String) # যেমন: "March 2026 Monthly Fee" বা "Annual Picnic 2026"
    amount = Column(Float)
    paid_amount = Column(Float, default=0.0)
    
    is_fined = Column(Boolean, default=False)
    fine_amount = Column(Float, default=0.0)
    fine_paid_amount = Column(Float, default=0.0)

    is_fined_waived = Column(Boolean, default=False)
    fine_waive_reason = Column(String, nullable=True) # কেন মওকুফ করা হলো
    fine_waived_at = Column(DateTime, nullable=True) # কখন মওকুফ করা হলো
    due_date = Column(DateTime) # এই তারিখের পর জরিমানা শুরু হবে
    is_paid = Column(Boolean, default=False)
    status = Column(String, default="Unpaid")

    member = relationship("Member")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"))
    amount_received = Column(Float) # মেম্বার কত টাকা ক্যাশ দিল
    payment_date = Column(DateTime, server_default=func.now())
    payment_method = Column(String, default="Cash") # Cash, Bkash, Bank
    receipt_no = Column(String, unique=True) # যেমন: MR-2026-001
    note = Column(String, nullable=True)

    member = relationship("Member")    

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Categories: Land, Building, Equipment, Vehicle, Other
    category = Column(String, nullable=False) 
    purchase_date = Column(Date, nullable=False)
    purchase_amount = Column(Float, nullable=False)
    funding_source = Column(String) # General Fund, Member Donation, etc.
    description = Column(String)
    document_path = Column(String, nullable=True) # ফাইলের লোকেশন

    # Depreciation লজিক
    # Methods: "Straight-Line", "None"
    depreciation_method = Column(String, default="None")
    useful_life_years = Column(Integer, default=0) # আয়ুষ্কাল
    salvage_value = Column(Float, default=0.0) # ভগ্নাবশেষ মূল্য
    
    # Financial Status
    current_book_value = Column(Float)
    is_disposed = Column(Boolean, default=False) # বিক্রি বা নষ্ট হয়েছে কিনা
    disposal_date = Column(Date, nullable=True)
    disposal_amount = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Expenses-এর সাথে লিঙ্ক (পরবর্তীতে ব্যবহারের জন্য)
    #expenses = relationship("Expense", back_populates="asset")    

