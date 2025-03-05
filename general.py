from flask import Flask, render_template, request, redirect, url_for
import qrcode
import os
from cryptography.fernet import Fernet
import cv2
import datetime
import sqlite3

KEY_FILE = "secret.key"
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)
else:
    with open(KEY_FILE, "rb") as key_file:
        key = key_file.read()

encryptor = Fernet(key)

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('attendance.sql3')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (timestamp TEXT, name TEXT, surname TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_qr():
    name = request.form['name']
    surname = request.form['surname']
    
    data = f"{name},{surname}"
    encrypted_data = encryptor.encrypt(data.encode()).decode()
    
    filename = f"static/qr_codes/{name.lower()}_{surname.lower()}_qr.png"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(encrypted_data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    img.save(filename)

    return render_template('index.html', qr_code=filename)

@app.route('/scan', methods=['GET', 'POST'])
def scan_qr():
    if request.method == 'POST':
        qr_code = request.form['qr_code']
        decrypted_data = encryptor.decrypt(qr_code.encode()).decode()
        name, surname = decrypted_data.split(',')
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect('attendance.sql3')
        c = conn.cursor()
        c.execute("INSERT INTO attendance (timestamp, name, surname) VALUES (?, ?, ?)", 
                  (timestamp, name, surname))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('scan.html')

@app.route('/records')
def records():
    conn = sqlite3.connect('attendance.sql3')
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    records = c.fetchall()
    conn.close()
    return render_template('records.html', records=records)

if __name__ == '__main__':
    app.run()