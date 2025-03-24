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
    conn = sqlite3.connect('attendance.db')
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
    try:
        name = request.form['name']
        surname = request.form['surname']
        
        # Validación básica de datos
        if not name or not surname:
            return render_template('index.html', error="El nombre y apellido son obligatorios")
        
        data = f"{name},{surname}"
        encrypted_data = encryptor.encrypt(data.encode()).decode()
        
        filename = f"static/qr_codes/{name.lower()}_{surname.lower()}_qr.png"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(encrypted_data)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        img.save(filename)

        conn = None
        try:
            conn = sqlite3.connect('attendance.db')
            c = conn.cursor()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO attendance (timestamp, name, surname) VALUES (?, ?, ?)", 
                    (timestamp, name, surname))
            conn.commit()
            return render_template('index.html', qr_code=filename)
        except sqlite3.Error as e:
            return render_template('index.html', error=f"Error en la base de datos: {str(e)}")
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return render_template('index.html', error=f"Error: {str(e)}")

@app.route('/scan', methods=['GET', 'POST'])
def scan_qr():
    if request.method == 'POST':
        try:
            qr_code = request.form['qr_code']
            if not qr_code:
                return render_template('scan.html', error="No se proporcionó código QR")
                
            decrypted_data = encryptor.decrypt(qr_code.encode()).decode()
            name, surname = decrypted_data.split(',')
            
            conn = None
            try:
                conn = sqlite3.connect('attendance.db')
                c = conn.cursor()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO attendance (timestamp, name, surname) VALUES (?, ?, ?)", 
                        (timestamp, name, surname))
                conn.commit()
                return redirect(url_for('index'))
            except sqlite3.Error as e:
                return render_template('scan.html', error=f"Error en la base de datos: {str(e)}")
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            return render_template('scan.html', error=f"Error: {str(e)}")

    return render_template('scan.html')

@app.route('/records')
def records():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT rowid, * FROM attendance")
    records = c.fetchall()
    conn.close()
    return render_template('records.html', records=records)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_record(id):
    try:
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE rowid = ?", (id,))
        conn.commit()
        conn.close()
        return redirect(url_for('records'))
    except sqlite3.Error as e:
        return render_template('records.html', error=f"Error al eliminar: {str(e)}")

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_record(id):
    if request.method == 'POST':
        try:
            name = request.form['name']
            surname = request.form['surname']
            timestamp = request.form['timestamp']
            
            if not name or not surname or not timestamp:
                return render_template('edit.html', error="Todos los campos son obligatorios")
            
            conn = sqlite3.connect('attendance.db')
            c = conn.cursor()
            c.execute("""
                UPDATE attendance 
                SET name = ?, surname = ?, timestamp = ?
                WHERE rowid = ?
            """, (name, surname, timestamp, id))
            conn.commit()
            conn.close()
            return redirect(url_for('records'))
        except sqlite3.Error as e:
            return render_template('edit.html', error=f"Error al actualizar: {str(e)}")
    else:
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute("SELECT * FROM attendance WHERE rowid = ?", (id,))
        record = c.fetchone()
        conn.close()
        return render_template('edit.html', record=record)

if __name__ == '__main__':
    app.run()