import psycopg2
from app.config import settings

conn = psycopg2.connect(
    host=settings.POSTGRES_HOST,
    port=settings.POSTGRES_PORT,
    user=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    database=settings.POSTGRES_DB
)
cur = conn.cursor()

cur.execute("SELECT id, project_name, uploaded_file_path, original_filename, status FROM draft_estimation_sessions")
rows = cur.fetchall()
print("\n--- DRAFT ESTIMATION SESSIONS ---")
for r in rows:
    print(f"id: {r[0]}, project_name: {r[1]}, uploaded_file_path: {r[2]}, original_filename: {r[3]}, status: {r[4]}")
    
cur.close()
conn.close()
