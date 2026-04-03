import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url.startswith("postgresql"):
    print("Not using PostgreSQL, exiting migration.")
    exit(0)

print(f"Connecting to {db_url}...")
conn = psycopg2.connect(db_url)
conn.autocommit = True
cursor = conn.cursor()

try:
    print("Migrating cart_items...")
    cursor.execute("ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS search_query VARCHAR;")
    cursor.execute("ALTER TABLE cart_items ALTER COLUMN product_name DROP NOT NULL;")
    cursor.execute("UPDATE cart_items SET search_query = product_name WHERE search_query IS NULL;")
    cursor.execute("ALTER TABLE cart_items ALTER COLUMN search_query SET NOT NULL;")

    print("Migrating price_snapshots...")
    cursor.execute("ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS search_query VARCHAR;")
    cursor.execute("UPDATE price_snapshots SET search_query = product_name WHERE search_query IS NULL;")
    cursor.execute("ALTER TABLE price_snapshots ALTER COLUMN search_query SET NOT NULL;")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_price_snapshots_search_query ON price_snapshots(search_query);")

    print("Migration completed successfully.")
except Exception as e:
    print(f"Error during migration: {e}")
finally:
    cursor.close()
    conn.close()
