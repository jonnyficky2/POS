import sqlite3

conn = sqlite3.connect("database.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transaksi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT,
    kasir TEXT,
    total INTEGER
)
""")

conn.commit()
conn.close()

print("Database berhasil dibuat")