import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

try:
    conn = engine.connect()
    print("✅ PostgreSQL Connected Successfully")
    conn.close()
except Exception as e:
    print("❌ Connection Failed:", e)