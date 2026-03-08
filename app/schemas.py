from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class MemberBase(BaseModel):
    member_code: str  # e.g., CF-101 (এটি ইউনিক হওয়া উচিত)
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    nid: Optional[str] = None
    share_count: int = 1

class MemberCreate(MemberBase):
    pass  # মেম্বার তৈরির সময় উপরের সব ফিল্ড লাগবে

class MemberResponse(MemberBase):
    id: int # ডাটাবেসের ইন্টারনাল আইডি
    advance_balance: float
    total_fine_charged: float
    total_fine_paid: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# class GenerateDueRequest(BaseModel):
#     month: int
#     year: int
#     rate_per_share: float


# ১. মান্থলি কন্ট্রিবিউশন এর জন্য
class MonthlyBillRequest(BaseModel):
    billing_period: str
    rate_per_share: float
    due_date: Optional[datetime] = None # না দিলে আমরা ডিফল্ট ১৫ তারিখ সেট করব

# ২. স্পেশাল বা ফিক্সড চার্জের জন্য
class SpecialChargeRequest(BaseModel):
    bill_name: str
    description: str # যেমন: "Annual Picnic 2026"
    amount: float
    is_per_share: bool = True # True হলে শেয়ার দিয়ে গুণ হবে, False হলে ফিক্সড
    due_date: datetime

# মেম্বারের সংক্ষিপ্ত তথ্যের জন্য
class MemberMini(BaseModel):
    name: str
    member_code: str

    class Config:
        from_attributes = True

class MonthlyBillResponse(BaseModel):
    id: int
    member_id: int
    billing_period: str
    amount: float
    paid_amount: float
    fine_amount:float
    fine_paid_amount:float
    due_date: datetime
    is_paid: bool
    status: str
    member: MemberMini 

    class Config:
        from_attributes = True

class SpecialBillResponse(BaseModel):
    id: int
    member_id: int
    bill_name: str
    description: Optional[str]
    amount: float
    due_date: datetime
    is_paid: bool
    status: Optional[str] 
    member: MemberMini 

    class Config:
        from_attributes = True


class WaiverRequest(BaseModel):
    member_code: str
    billing_period: Optional[str] = None # মান্থলি বিলের জন্য (যেমন: 2026-03)
    bill_name: Optional[str] = None      # স্পেশাল বিলের জন্য
    reason: str                          # অডিট ট্রেইল এর জন্য কারণ বাধ্যতামূলক