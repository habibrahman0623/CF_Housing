from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, auth_utils
from app.dependencies import get_current_user, check_admin

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong Password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_utils.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

from app.auth_utils import get_password_hash

@router.post("/create-user", dependencies=[Depends(check_admin)])
def create_new_user(username: str, password: str, role: str = "operator", db: Session = Depends(get_db)):
    # ইউজার আগে থেকেই আছে কিনা চেক
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="এই ইউজারনেমটি ইতিমধ্যে ব্যবহৃত হয়েছে।")

    # পাসওয়ার্ড হ্যাশ করে সেভ করা
    new_user = models.User(
        username=username,
        hashed_password=get_password_hash(password),
        role=role
    )
    db.add(new_user)
    db.commit()
    return {"message": f"User {username} created successfully as {role}"}

@router.put("/admin/reset-password/{user_id}", dependencies=[Depends(check_admin)])
def admin_reset_password(
    user_id: int, 
    new_password: str, 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found")

    user.hashed_password = auth_utils.get_password_hash(new_password)
    db.commit()
    return {"message": f"User {user.username}-Password has been reset successfully"}

@router.put("/me/change-password")
def change_my_password(
    old_password: str, 
    new_password: str, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # বর্তমান পাসওয়ার্ড চেক করা
    if not auth_utils.verify_password(old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Wrong Password")

    # নতুন পাসওয়ার্ড হ্যাশ করে সেভ করা
    current_user.hashed_password = auth_utils.get_password_hash(new_password)
    db.commit()
    return {"message": "Your password has been changed successfully"}

