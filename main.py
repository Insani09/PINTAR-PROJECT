# main.py
import os
import base64
import hashlib
import datetime
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, jsonify, flash, Response
import mysql.connector
import cv2
import numpy as np
from werkzeug.utils import secure_filename
from io import BytesIO
from xhtml2pdf import pisa  # Memakai xhtml2pdf agar 100% aman di Windows/Laragon

app = Flask(__name__)
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
        # 1. Decode webcam image
        encoded_data = base64_webcam.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img_webcam = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
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
                
            # Ambil wajah pertama yang terdeteksi (x, y, lebar, tinggi)
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w] # Crop hanya area wajah
            
            # Resize ke ukuran standar untuk dibandingkan
            return cv2.resize(face_roi, (150, 150))

        # 4. Ambil wajah dari kedua gambar
        face_webcam = get_face_only(img_webcam)
        face_master = get_face_only(img_master)
        
        if face_webcam is None:
            return False, "Kamera tidak mendeteksi wajah (Coba geser posisi)!"
        if face_master is None:
            return False, "Foto master tidak valid (Wajah tidak terlihat jelas)!"
            
        # 5. Bandingkan HANYA bagian wajahnya saja
        diff = cv2.absdiff(face_webcam, face_master)
        non_zero_count = np.count_nonzero(diff > 30) # Toleransi perbedaan cahaya ruangan
        total_pixels = 150 * 150
        
        # Hitung persentase ketidakmiripan (error rate)
        error_rate = (non_zero_count / total_pixels) * 100
        match_score = max(0, 100 - error_rate)
        
        # Threshold: Jika tingkat error di bawah 45%, maka dianggap wajah yang sama
        if error_rate < 45:
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
    
    # Handle Tambah Siswa (POST)
    if request.method == 'POST' and 'tambah_siswa' in request.form:
        id_card = request.form['id_card']
        nama = request.form['nama']
        nisn = request.form['nisn']
        kelas = request.form['kelas']
        agama = request.form['agama']
        file_foto = request.files['foto_master']
        
        if file_foto:
            filename = secure_filename(f"{nisn}_{file_foto.filename}")
            file_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], 'siswa', filename))
            
            try:
                cursor.execute("""
                    INSERT INTO siswa (id_card, nama, nisn, kelas, agama, foto_master)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_card, nama, nisn, kelas, agama, filename))
                conn.commit()
                flash("Data siswa berhasil disimpan!", "success")
            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
        else:
            flash("Foto master AI wajib diunggah.", "danger")
            
        return redirect(url_for('dashboard'))

    # Ambil Statistik Ringkasan
    cursor.execute("SELECT COUNT(*) as total FROM siswa")
    total_siswa = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as hadir FROM absensi WHERE DATE(waktu_hadir) = CURDATE() AND keterangan LIKE '%Verified%'")
    total_hadir = cursor.fetchone()['hadir']

    cursor.execute("SELECT COUNT(*) as gagal FROM absensi WHERE DATE(waktu_hadir) = CURDATE() AND (keterangan LIKE '%Gagal%' OR keterangan LIKE '%Tidak Identik%')")
    total_gagal = cursor.fetchone()['gagal']

    # Ambil Data Master Siswa
    cursor.execute("SELECT * FROM siswa ORDER BY nama ASC")
    data_siswa = cursor.fetchall()
    
    # Ambil Live Log Kehadiran
    cursor.execute("""
        SELECT absensi.*, siswa.nama, siswa.kelas 
        FROM absensi 
        JOIN siswa ON absensi.siswa_id = siswa.id 
        ORDER BY absensi.waktu_hadir DESC LIMIT 10
    """)
    log_absensi = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', 
                           siswa=data_siswa, 
                           log_absensi=log_absensi,
                           stats={'total': total_siswa, 'hadir': total_hadir, 'gagal': total_gagal})

@app.route('/hapus_siswa/<int:id>')
def hapus_siswa(id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT foto_master FROM siswa WHERE id = %s", (id,))
    siswa = cursor.fetchone()
    if siswa and siswa['foto_master']:
        path_foto = os.path.join(app.config['UPLOAD_FOLDER'], 'siswa', siswa['foto_master'])
        if os.path.exists(path_foto):
            os.remove(path_foto)
            
    cursor.execute("DELETE FROM siswa WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Data siswa berhasil dihapus!", "success")
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

# --- ROUTE UNTUK HALAMAN BARU ---

@app.route('/aktivitas_terbaru')
def aktivitas_terbaru():
    if 'admin_id' not in session: return redirect(url_for('login'))
    
    # Ambil halaman saat ini untuk navigasi
    page = int(request.args.get('page', 1))
    offset = (page - 1) * 10
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Ambil 10 data terbaru
    cursor.execute("""
        SELECT absensi.*, siswa.nama, siswa.kelas 
        FROM absensi 
        JOIN siswa ON absensi.siswa_id = siswa.id 
        ORDER BY absensi.waktu_hadir DESC LIMIT 10 OFFSET %s
    """, (offset,))
    logs = cursor.fetchall()
    cursor.close(); conn.close()
    
    return render_template('aktivitas.html', logs=logs, page=page)

@app.route('/edit_siswa/<int:id>', methods=['POST'])
def edit_siswa(id):
    if 'admin_id' not in session: return redirect(url_for('login'))
    # Logika UPDATE siswa SET ... WHERE id = id
    flash("Data siswa berhasil diperbarui!", "success")
    return redirect(url_for('dashboard'))

# ==========================================
# REPORT GENERATOR ENGINE
# ==========================================
@app.route('/export_pdf')
def export_pdf():
    nama_pembina = request.args.get('nama_pembina', 'M. Adrian Kurniawan, S.Pd.')
    nip_pembina = request.args.get('nip_pembina', '19850311 201001 2 003')
    filter_ibadah = request.args.get('filter_ibadah', 'Semua')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if filter_ibadah == 'Semua':
        cursor.execute("""
            SELECT absensi.*, siswa.nama, siswa.kelas, siswa.nisn 
            FROM absensi 
            JOIN siswa ON absensi.siswa_id = siswa.id 
            ORDER BY absensi.waktu_hadir DESC
        """)
    else:
        cursor.execute("""
            SELECT absensi.*, siswa.nama, siswa.kelas, siswa.nisn 
            FROM absensi 
            JOIN siswa ON absensi.siswa_id = siswa.id 
            WHERE absensi.jenis_ibadah = %s
            ORDER BY absensi.waktu_hadir DESC
        """, (filter_ibadah,))
        
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    html_template = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {
                size: a4;
                margin: 20mm 15mm 20mm 15mm;
            }
            body { 
                font-family: 'Times New Roman', Times, serif; 
                color: #000000; 
                line-height: 1.4; 
            }
            .kop { text-align: center; border-bottom: 3px double #000000; padding-bottom: 6px; margin-bottom: 20px; }
            .kop h1 { font-size: 14pt; text-transform: uppercase; margin: 0; font-weight: bold; }
            .kop h2 { font-size: 16pt; text-transform: uppercase; margin: 5px 0 0 0; font-weight: bold; }
            .kop h3 { font-size: 11pt; margin: 5px 0 0 0; font-weight: normal; font-style: italic; }
            .kop p { font-size: 9pt; margin: 5px 0 0 0; font-style: italic; }
            
            .title-dokumen { text-align: center; margin-bottom: 25px; }
            .title-dokumen h4 { font-size: 12pt; text-transform: uppercase; margin: 0; font-weight: bold; }
            .title-dokumen p { font-size: 10pt; margin: 5px 0 0 0; }
            
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th { border: 1px solid #000000; background-color: #f3f4f6; padding: 8px; font-weight: bold; text-transform: uppercase; font-size: 10pt; text-align: center; }
            td { border: 1px solid #000000; padding: 6px; font-size: 10pt; vertical-align: middle; }
            .text-center { text-align: center; }
            
            .ttd-container { width: 100%; margin-top: 30px; }
            .ttd-table { width: 100%; border: none; }
            .ttd-table td { border: none; width: 50%; font-size: 11pt; padding: 0; }
            .nama-pembina { font-weight: bold; text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="kop">
            <h1>Pemerintah Provinsi Jawa Timur</h1>
            <h2>Dinas Pendidikan - SMKN 1 Surabaya</h2>
            <h3>Kompetensi Keahlian: Rekayasa Perangkat Lunak (RPL)</h3>
            <p>JL. SMEA NO. 4 WONOKROMO, Wonokromo, Kec. Wonokromo, Kota Surabaya, Jawa Timur</p>
        </div>
        
        <div class="title-dokumen">
            <h4>Laporan Rekapitulasi Kehadiran Pembiasaan Ibadah Siswa</h4>
            <p>Sistem PINTAR (RFID & Webcam AI Auto-Verification) &mdash; Filter: {{ filter_ibadah }}</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 5%;">No</th>
                    <th style="width: 20%;">NISN</th>
                    <th style="width: 35%;">Nama Siswa</th>
                    <th style="width: 15%;">Kelas</th>
                    <th style="width: 25%;">Sesi Ibadah</th>
                </tr>
            </thead>
            <tbody>
                {% for log in logs %}
                <tr>
                    <td class="text-center">{{ loop.index }}</td>
                    <td class="text-center">{{ log.nisn }}</td>
                    <td><b>{{ log.nama }}</b></td>
                    <td class="text-center">{{ log.kelas }}</td>
                    <td class="text-center">{{ log.jenis_ibadah }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="ttd-container">
            <table class="ttd-table">
                <tr>
                    <td></td>
                    <td style="text-align: left; padding-left: 120px;">
                        Surabaya, {{ tanggal_hari_ini }}<br>
                        Mengetahui,<br>
                        Guru Pembina Ibadah
                        <br><br><br><br>
                        <span class="nama-pembina">{{ nama_pembina }}</span><br>
                        NIP. {{ nip_pembina }}
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
    
    tgl = datetime.datetime.now().strftime("%d %B %Y")
    rendered_html = render_template_string(
        html_template, 
        logs=logs, 
        nama_pembina=nama_pembina, 
        nip_pembina=nip_pembina, 
        filter_ibadah=filter_ibadah, 
        tanggal_hari_ini=tgl
    )
    
    pdf_buffer = BytesIO()
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