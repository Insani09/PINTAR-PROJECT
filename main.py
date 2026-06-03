import os
import base64
import hashlib
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
import mysql.connector
import cv2
import numpy as np
from werkzeug.utils import secure_filename
from io import BytesIO
from xhtml2pdf import pisa  # Memakai xhtml2pdf agar 100% aman di Windows/Laragon

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = "super_secret_key_pintar_rpl_2026"
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Pastikan folder upload ada
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'siswa'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'laporan'), exist_ok=True)

# Fungsi Helper Koneksi Database
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ta_pintar"
    )

# ==========================================
# ENGINE AI: VERIFIKASI WAJAH (OPENCV HAAR CASCADE)
# ==========================================
# Inisialisasi Pendeteksi Wajah Bawaan OpenCV
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def verify_face(base64_webcam, filename_master):
    try:
        # 1. Decode webcam image (dengan pengamanan format)
        if ',' in base64_webcam:
            encoded_data = base64_webcam.split(',')[1]
        else:
            return False, "Format gambar dari kamera tidak valid"
            
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img_webcam = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Penting: Balik gambar webcam secara horizontal agar orientasinya sama dengan foto master (tidak mirrored)
        img_webcam = cv2.flip(img_webcam, 1)
        
        # 2. Load Master Image
        path_master = os.path.join(app.config['UPLOAD_FOLDER'], 'siswa', filename_master)
        if not os.path.exists(path_master): 
            return False, "Master Foto Hilang"
        img_master = cv2.imread(path_master)
        
        # 3. Fungsi Khusus: Cari dan potong bagian wajahnya saja
        def get_face_only(img):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Deteksi posisi wajah
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
            
            if len(faces) == 0:
                return None # Wajah tidak ditemukan di gambar
                
            # Ambil wajah dengan ukuran TERBESAR (menghindari deteksi palsu/background noise)
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w] # Crop hanya area wajah
            
            # Resize ke ukuran standar untuk dibandingkan
            resized = cv2.resize(face_roi, (150, 150))
            # Histogram Equalization untuk normalisasi cahaya wajah
            return cv2.equalizeHist(resized)

        # 4. Ambil wajah dari kedua gambar
        face_webcam = get_face_only(img_webcam)
        face_master = get_face_only(img_master)
        
        if face_webcam is None:
            return False, "Kamera tidak mendeteksi wajah (Coba geser posisi)!"
        if face_master is None:
            return False, "Foto master tidak valid (Wajah tidak terlihat jelas)!"
            
        # 5. Bandingkan menggunakan Normalized Template Matching (TM_CCOEFF_NORMED)
        # Crop bagian tengah wajah master (110x110) sebagai template
        template = face_master[20:130, 20:130]
        res = cv2.matchTemplate(face_webcam, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        
        match_score = max(0.0, max_val) * 100
        
        # Threshold kecocokan diatur ke 35% (cukup ketat untuk wajah, namun toleran cahaya/posisi)
        if match_score >= 35:
            return True, f"Verified ({int(match_score)}%)"
        else:
            return False, f"Wajah Tidak Identik ({int(match_score)}%)"
            
    except Exception as e:
        return False, f"AI Error: {str(e)}"

# ==========================================
# ROUTING & CONTROLLER APPLICATION
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['target_agama'] = request.form['target_agama']
        session['sesi_ibadah'] = request.form['sesi_ibadah']
        return redirect(url_for('absen'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password_hash))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin:
            session['admin_id'] = admin['id']
            session['admin_nama'] = admin['nama_lengkap']
            return redirect(url_for('dashboard'))
        else:
            flash("Username atau Password salah!", "danger")
    return render_template('login.html')

@app.route('/hapus_log/<int:id>', methods=['POST'])
def hapus_log(id):
    if 'admin_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    username = request.form.get('username')
    password = request.form.get('password')
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verifikasi kredensial admin
    cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password_hash))
    admin = cursor.fetchone()

    if admin:
        cursor.execute("DELETE FROM absensi WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Log berhasil dihapus!", "success")
        return redirect(url_for('dashboard'))
    else:
        cursor.close()
        conn.close()
        flash("Username atau Password Admin salah!", "danger")
        return redirect(url_for('dashboard'))
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # --- 1. HANDLE TAMBAH SISWA (POST) ---
    if request.method == 'POST' and 'tambah_siswa' in request.form:
        id_card = request.form['id_card']
        nama = request.form['nama']
        nisn = request.form['nisn']
        kelas = request.form['kelas']
        agama = request.form['agama']
        jenis_kelamin = request.form['jenis_kelamin']
        file_foto = request.files['foto_master']
        
        if file_foto:
            filename = secure_filename(f"{nisn}_{file_foto.filename}")
            file_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], 'siswa', filename))
            
            try:
                cursor.execute("""
                    INSERT INTO siswa (id_card, nama, nisn, kelas, agama, jenis_kelamin, foto_master)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_card, nama, nisn, kelas, agama, jenis_kelamin, filename))
                conn.commit()
                flash("Data siswa berhasil disimpan!", "success")
            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
        else:
            flash("Foto master AI wajib diunggah.", "danger")
            
        return redirect(url_for('dashboard'))

    # --- 2. AMBIL STATISTIK HARI INI ---
    # Total Siswa Terdaftar
    cursor.execute("SELECT COUNT(*) as total FROM siswa")
    total_siswa = cursor.fetchone()['total']
    
    # Hadir (Verified)
    cursor.execute("""
        SELECT COUNT(*) as hadir 
        FROM absensi 
        WHERE DATE(waktu_hadir) = CURDATE() 
        AND keterangan LIKE '%Verified%'
    """)
    total_hadir = cursor.fetchone()['hadir']

    # Gagal
    cursor.execute("""
        SELECT COUNT(*) as gagal 
        FROM absensi 
        WHERE DATE(waktu_hadir) = CURDATE() 
        AND keterangan NOT LIKE '%Verified%'
    """)
    total_gagal = cursor.fetchone()['gagal']

    # --- 3. AMBIL DATA MASTER SISWA ---
    cursor.execute("SELECT * FROM siswa ORDER BY nama ASC")
    data_siswa = cursor.fetchall()
    
    # --- 4. AMBIL LIVE LOG KEHADIRAN (10 TERAKHIR) ---
    cursor.execute("""
        SELECT absensi.*, siswa.nama, siswa.kelas 
        FROM absensi 
        JOIN siswa ON absensi.siswa_id = siswa.id 
        ORDER BY absensi.waktu_hadir DESC LIMIT 10
    """)
    log_absensi = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Kirim semua data ke template
    return render_template('dashboard.html', 
                           siswa=data_siswa, 
                           log_absensi=log_absensi,
                           stats={
                               'total': total_siswa, 
                               'hadir': total_hadir, 
                               'gagal': total_gagal
                           })

# --- FUNGSI HAPUS AKTIVITAS YANG SUDAH DIGABUNGKAN ---
@app.route('/hapus_aktivitas/<int:id>')
def hapus_aktivitas(id):
    if 'admin_id' not in session: 
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM absensi WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Log aktivitas berhasil dihapus!", "success")
    except Exception as e:
        flash(f"Error saat menghapus aktivitas: {e}", "danger")
        
    # Redirect kembali ke halaman asal (dashboard atau halaman aktivitas terbaru)
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/aktivitas_terbaru')
def aktivitas_terbaru():
    if 'admin_id' not in session: return redirect(url_for('login'))
    
    # Ambil halaman saat ini (default halaman 1)
    page = int(request.args.get('page', 1))
    limit = 5 # Batasi HANYA 5 data per halaman
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Hitung total data untuk mengetahui jumlah maksimal halaman
    cursor.execute("SELECT COUNT(*) as total FROM absensi")
    total_data = cursor.fetchone()['total']
    total_pages = (total_data + limit - 1) // limit if total_data > 0 else 1
    
    # Ambil 5 data terbaru sesuai halaman
    cursor.execute("""
        SELECT absensi.*, siswa.nama, siswa.kelas 
        FROM absensi 
        JOIN siswa ON absensi.siswa_id = siswa.id 
        ORDER BY absensi.waktu_hadir DESC LIMIT %s OFFSET %s
    """, (limit, offset))
    logs = cursor.fetchall()
    cursor.close(); conn.close()
    
    return render_template('aktivitas.html', logs=logs, page=page, total_pages=total_pages)

@app.route('/edit_siswa/<int:id>', methods=['POST'])
def edit_siswa(id):
    if 'admin_id' not in session: 
        return redirect(url_for('login'))
        
    id_card = request.form.get('id_card')
    nama = request.form.get('nama')
    nisn = request.form.get('nisn')
    kelas = request.form.get('kelas')
    agama = request.form.get('agama')
    jenis_kelamin = request.form.get('jenis_kelamin')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE siswa 
            SET id_card=%s, nama=%s, nisn=%s, kelas=%s, agama=%s, jenis_kelamin=%s 
            WHERE id=%s
        """, (id_card, nama, nisn, kelas, agama, jenis_kelamin, id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Data siswa berhasil diperbarui!", "success")
    except Exception as e:
        flash(f"Gagal memperbarui data: Pastikan UID RFID atau NISN belum dipakai siswa lain.", "danger")
        
    return redirect(url_for('dashboard'))

@app.route('/hapus_siswa/<int:id>')
def hapus_siswa(id):
    # Pastikan admin sudah login
    if 'admin_id' not in session: 
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Hapus file foto master jika ada
        cursor.execute("SELECT foto_master FROM siswa WHERE id = %s", (id,))
        siswa = cursor.fetchone()
        if siswa and siswa[0]:
            path_foto = os.path.join(app.config['UPLOAD_FOLDER'], 'siswa', siswa[0])
            if os.path.exists(path_foto):
                os.remove(path_foto)

        # Eksekusi query untuk menghapus data berdasarkan ID
        cursor.execute("DELETE FROM siswa WHERE id = %s", (id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        flash("Data siswa berhasil dihapus!", "success")
    except Exception as e:
        flash(f"Gagal menghapus data siswa. Error: {e}", "danger")
        
    # Kembalikan halaman ke dashboard setelah proses selesai
    return redirect(url_for('dashboard'))

@app.route('/absen', methods=['GET', 'POST'])
def absen():
    if 'sesi_ibadah' not in session:
        flash("Silakan konfigurasi sesi ibadah terlebih dahulu!", "warning")
        return redirect(url_for('index'))
        
    status_msg = None
    status_type = "standby"
    
    if request.method == 'POST':
        id_card = request.form.get('id_card')
        snapshot_base64 = request.form.get('snapshot')
        sesi_aktif = session.get('sesi_ibadah')
        target_agama = session.get('target_agama')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM siswa WHERE id_card = %s", (id_card,))
        siswa = cursor.fetchone()
        
        if not siswa:
            status_msg = f"Gagal! Kartu RFID ({id_card}) Tidak Terdaftar!"
            status_type = "danger"
        elif siswa['agama'].lower() != target_agama.lower():
            status_msg = f"Ditolak! Sesi ini khusus siswa beragama {target_agama}."
            status_type = "danger"
        else:
            if snapshot_base64 and siswa['foto_master']:
                is_valid_face, ai_message = verify_face(snapshot_base64, siswa['foto_master'])
                if is_valid_face:
                    cursor.execute("""
                        INSERT INTO absensi (siswa_id, jenis_ibadah, keterangan, foto) 
                        VALUES (%s, %s, %s, %s)
                    """, (siswa['id'], sesi_aktif, "Hadir Tepat Waktu (Verified)", snapshot_base64))
                    conn.commit()
                    status_msg = f"Berhasil Absen! Halo {siswa['nama']}. {ai_message}"
                    status_type = "success"
                else:
                    cursor.execute("""
                        INSERT INTO absensi (siswa_id, jenis_ibadah, keterangan, foto) 
                        VALUES (%s, %s, %s, %s)
                    """, (siswa['id'], sesi_aktif, f"Autentikasi Gagal: {ai_message}", snapshot_base64))
                    conn.commit()
                    status_msg = f"ABSEN DITOLAK! {ai_message}"
                    status_type = "danger"
            else:
                status_msg = "Gagal! Kamera terganggu atau foto master belum di-upload."
                status_type = "danger"
                
        cursor.close()
        conn.close()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": status_type, "message": status_msg})

    return render_template('absen.html', 
                           sesi_ibadah=session['sesi_ibadah'], 
                           target_agama=session['target_agama'],
                           status_msg=status_msg,
                           status_type=status_type)

@app.route('/pengaturan_pdf')
def pengaturan_pdf():
    # Proteksi halaman agar hanya admin yang bisa akses
    if 'admin_id' not in session: 
        return redirect(url_for('login'))
        
    return render_template('pengaturan_pdf.html')

# ==========================================
# REPORT GENERATOR ENGINE
# ==========================================
@app.route('/export_pdf')
def export_pdf():
    # Ambil parameter jika ada, default diatur ke Pembina
    nama_pembina = request.args.get('nama_pembina', 'Vania Afrin Santoso, S.Pd.')
    nip_pembina = request.args.get('nip_pembina', '2008290401234')
    filter_ibadah = request.args.get('filter_ibadah', 'Semua')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if filter_ibadah == 'Semua':
        cursor.execute("""
            SELECT MAX(absensi.waktu_hadir) as waktu_hadir, 
                   absensi.jenis_ibadah, 
                   absensi.keterangan, 
                   siswa.nama, 
                   siswa.kelas, 
                   siswa.nisn 
            FROM absensi 
            JOIN siswa ON absensi.siswa_id = siswa.id 
            WHERE absensi.keterangan LIKE '%Verified%'
            GROUP BY siswa.id, siswa.nama, siswa.kelas, siswa.nisn, absensi.jenis_ibadah, absensi.keterangan
            ORDER BY waktu_hadir DESC
        """)
    else:
        cursor.execute("""
            SELECT MAX(absensi.waktu_hadir) as waktu_hadir, 
                   absensi.jenis_ibadah, 
                   absensi.keterangan, 
                   siswa.nama, 
                   siswa.kelas, 
                   siswa.nisn 
            FROM absensi 
            JOIN siswa ON absensi.siswa_id = siswa.id 
            WHERE absensi.jenis_ibadah = %s 
            AND absensi.keterangan LIKE '%Verified%'
            GROUP BY siswa.id, siswa.nama, siswa.kelas, siswa.nisn, absensi.jenis_ibadah, absensi.keterangan
            ORDER BY waktu_hadir DESC
        """, (filter_ibadah,))
        
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Format tanggal untuk TTD
    tgl = datetime.datetime.now().strftime("%d %B %Y")
    
    # Gunakan render_template() langsung ke file cetak_pdf.html
    rendered_html = render_template(
        'cetak_pdf.html', 
        logs=logs, 
        nama_pembina=nama_pembina, 
        nip_pembina=nip_pembina, 
        filter_ibadah=filter_ibadah, 
        tanggal_hari_ini=tgl
    )
    
    pdf_buffer = BytesIO()
    # Panggil fungsi xhtml2pdf
    pisa_status = pisa.CreatePDF(rendered_html, dest=pdf_buffer)
    
    if pisa_status.err:
        return "Gagal melakukan generate PDF", 500
        
    pdf_buffer.seek(0)
    return Response(
        pdf_buffer.getvalue(), 
        mimetype='application/pdf', 
        headers={"Content-Disposition": "inline; filename=Laporan_PINTAR.pdf"}
    )

if __name__ == '__main__':
    app.run(debug=True, port=8080)