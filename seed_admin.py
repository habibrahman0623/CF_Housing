# seed_admin.py

from app.database import SessionLocal
from app import models, auth_utils

def create_initial_admin():
    db = SessionLocal()
    try:
        # চেক করা হচ্ছে এডমিন অলরেডি আছে কিনা
        admin_exists = db.query(models.User).filter(models.User.username == "admin").first()
        
        if not admin_exists:
            # প্রথম এডমিন তৈরি
            admin_user = models.User(
                username="admin",
                hashed_password=auth_utils.get_password_hash("admin123"), # আপনার সিকিউর পাসওয়ার্ড
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ Super Admin ('admin') created successfully!")
            print("🔑 Password is: admin123")
        else:
            print("⚠️ Admin user already exists. Skipping...")
            
    except Exception as e:
        print(f"❌ Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()