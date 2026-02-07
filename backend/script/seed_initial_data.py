import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 建立資料庫連線
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def seed_contacts():
    # 定義要初始化的用戶資料
    seed_data = [
        {'name': 'pkc', 'email': 'pkchc325@gmail.com', 'discord_id': '665386325985329162'},
        {'name': 'ivan', 'email': 'david103132881@gmail.com', 'discord_id': '812522692506943518'},
        {'name': '曾士珍', 'email': 'sjtseng.tw@gmail.com', 'discord_id': '868735361986220103'},
        # 如有更多用戶可在此添加
    ]

    print("Running initial data seeding for Contacts...")
    
    try:
        for row in seed_data:
            # 使用 PostgreSQL Upsert (ON CONFLICT)
            query = text("""
                INSERT INTO contacts (name, email, discord_id, is_active)
                VALUES (:name, :email, :discord_id, 1)
                ON CONFLICT (email) 
                DO UPDATE SET 
                    discord_id = EXCLUDED.discord_id,
                    name = EXCLUDED.name,
                    is_active = 1;
            """)
            db.execute(query, row)
        
        db.commit()
        print("Initial data seeding completed successfully.")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_contacts()
