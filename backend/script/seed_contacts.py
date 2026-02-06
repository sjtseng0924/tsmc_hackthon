import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Contact
from app.config import settings

# 建立資料庫連線
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# 定義要加入/更新的用戶資料
# 格式: (Name, Email, Discord_ID)
# Discord ID 必須是字串，如果要留空則寫 None
users_to_seed = [
    # (Name, Email, Discord_ID)
    ("pkc", "pkc776@gmail.com", "665386325985329162"), 
    ("ivan", "ivan@example.com", "812522692506943518"),
    # 如果系統中已有 kevin/david，可以手動補上他們的 ID
    # ("kevin", "kevin@example.com", None), 
]

print("開始更新 Contact 資料...")

try:
    for name, email, discord_id in users_to_seed:
        # 先用 email 找找看有沒有這個人
        contact = db.query(Contact).filter(Contact.email == email).first()
        
        if contact:
            print(f"更新現有用戶: {name} ({email})")
            if discord_id:
                contact.discord_id = discord_id
            contact.name = name # 更新名字以防萬一
        else:
            print(f"創建新用戶: {name} ({email})")
            contact = Contact(
                name=name,
                email=email,
                discord_id=discord_id,
                department="Engineering", # 預設部門
                is_active=1
            )
            db.add(contact)
        
    db.commit()
    print("資料更新成功！")
    
    # 顯示目前所有有 Discord ID 的用戶
    print("\n目前擁有 Discord ID 的用戶:")
    contacts = db.query(Contact).filter(Contact.discord_id != None).all()
    for c in contacts:
        print(f"- {c.name}: {c.email} (Discord: {c.discord_id})")

except Exception as e:
    print(f"發生錯誤: {e}")
    db.rollback()
finally:
    db.close()
