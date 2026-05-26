# setup_admin.py
import mysql.connector
import hashlib

def init_db():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password=""
    )
    cursor = db.cursor()
    
    # Mengganti nama database sesuai request baru
    cursor.execute("CREATE DATABASE IF NOT EXISTS ta_pintar")
    cursor.execute("USE ta_pintar")
    
    # Tabel Admin
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        nama_lengkap VARCHAR(100) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # Tabel Siswa
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS siswa (
        id INT PRIMARY KEY AUTO_INCREMENT,
        id_card VARCHAR(50) UNIQUE NOT NULL,
        nisn VARCHAR(20) UNIQUE NOT NULL,
        nama VARCHAR(100) NOT NULL,
        kelas VARCHAR(30) NOT NULL,
        jenis_kelamin ENUM('L', 'P') NOT NULL,
        agama VARCHAR(20) NOT NULL,
        foto_master VARCHAR(255) DEFAULT NULL
    )""")
    
    # Tabel Absensi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS absensi (
        id INT PRIMARY KEY AUTO_INCREMENT,
        siswa_id INT NOT NULL,
        jenis_ibadah VARCHAR(50) NOT NULL,
        waktu_hadir TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        keterangan VARCHAR(50) DEFAULT 'Hadir Tepat Waktu',
        foto LONGTEXT DEFAULT NULL,
        FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE
    )""")
    
    # Buat ulang akun admin fresh
    cursor.execute("DELETE FROM admin WHERE username = 'admin'")
    password_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute(
        "INSERT INTO admin (username, password, nama_lengkap) VALUES (%s, %s, %s)",
        ("admin", password_hash, "Administrator PINTAR")
    )
    db.commit()
    print("[SUCCESS] Database 'ta_pintar' berhasil dibuat!")
    print("-> Akun Login Utama -> Username: admin | Password: admin123")
        
    cursor.close()
    db.close()

if __name__ == "__main__":
    init_db()