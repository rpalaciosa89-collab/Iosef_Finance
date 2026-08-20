import sqlite3
from app.core.security import get_password_hash

new_hash = get_password_hash("admin123")
conn = sqlite3.connect("iosef_finance.db")
c = conn.cursor()
c.execute("UPDATE users SET hashed_password = ? WHERE email = 'admin@iosef.finance'", (new_hash,))
conn.commit()
conn.close()
print("Password updated to admin123")
