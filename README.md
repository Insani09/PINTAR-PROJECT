# 🎓 PINTAR

Personalized Intelligent Tracker for Attendance & Religion (PINTAR) is a web-based attendance management system that combines RFID card scanning with webcam-based face verification using OpenCV. It provides an admin dashboard, automatic PDF report generation, and student master photo uploads.

---

## Table of Contents
1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Getting Started](#getting-started)
4. [Project Structure](#project-structure)
5. [Notes & Tips](#notes--tips)
6. [Contributing & Contact](#contributing--contact)

---

## Features

- **Smart Attendance**: RFID scanning validated with real-time face verification (`verify_face()` in `main.py`).
- **Data Management**: Full student management, including uploading master ID photos.
- **Reporting**: Export attendance summaries to PDF.
- **Access Control**: Admin-only protected pages and role checks.

---

## Tech Stack

- Language: Python 3.10+
- Web framework: Flask (Werkzeug)
- Computer vision: OpenCV (`opencv-python`) & NumPy
- Database: MySQL (`mysql-connector-python`)
- PDF rendering: `xhtml2pdf`

---

## Getting Started

Follow these steps to run PINTAR locally.

1. Create a virtual environment (recommended):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configuration

- Update database credentials in the `get_db_connection()` function in `main.py` if needed.
- Ensure the following directories exist: `static/uploads/siswa` and `static/uploads/laporan`.

4. Initialize the database (optional / reset) and create a default admin account (username: `admin`, password: `admin123`):

```powershell
python setup_admin.py
```

5. Run the application:

```powershell
python main.py
```

Open your browser at: http://localhost:8080

---

## Project Structure

PINTAR/
- `static/` — dynamic uploads (student photos & generated PDFs)
- `templates/` — HTML templates
- `main.py` — Flask app, routes, face verification logic, PDF export
- `setup_admin.py` — DB setup script that creates default admin
- `requirements.txt` — Python dependencies

---

## Notes & Tips

- For best face recognition results, use clear master photos with neutral backgrounds and good lighting.
- If face detection fails frequently, adjust camera angle/lighting or tweak `minSize` and `scaleFactor` parameters in `face_cascade.detectMultiScale`.

---

## Contributing & Contact

Contributions are welcome: bug fixes, new features, or documentation improvements. Please create a feature branch, run tests locally, and open a Pull Request with a short description.

Creator: Insania Aura Ramadhani
Email: insaniauraramadhani@gmail.com