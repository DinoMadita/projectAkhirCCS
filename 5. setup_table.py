5. setup_table.py

import pymysql

conn = pymysql.connect(
    host="secure-cloud-drive-db.csuwiuoyz36c.us-east-1.rds.amazonaws.com",
    user="admin",
    password="CloudDrive123!",
    database="cloud_drive",
    port=3306
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_size INT,
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
print("Tabel 'files' berhasil dibuat!")

cursor.close()
conn.close()
