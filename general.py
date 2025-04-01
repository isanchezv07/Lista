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
    c.execute('''CREATE TABLE IF NOT EXISTS generation_records
                 (timestamp TEXT, name TEXT, surname TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scanning_records
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
            c.execute("INSERT INTO generation_records (timestamp, name, surname) VALUES (?, ?, ?)", 
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
                c.execute("INSERT INTO scanning_records (timestamp, name, surname) VALUES (?, ?, ?)", 
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
    c.execute("SELECT rowid, * FROM generation_records")
    generation_records = c.fetchall()
    c.execute("SELECT rowid, * FROM scanning_records")
    scanning_records = c.fetchall()
    conn.close()
    return render_template('records.html', generation_records=generation_records, scanning_records=scanning_records)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_record(id):
    try:
        table = request.form.get('table', 'generation_records')
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute(f"DELETE FROM {table} WHERE rowid = ?", (id,))
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
            table = request.form.get('table', 'generation_records')
            regenerate_qr = request.form.get('regenerate_qr') == '1'
            
            if not name or not surname or not timestamp:
                return render_template('edit.html', error="Todos los campos son obligatorios")
            
            conn = sqlite3.connect('attendance.db')
            c = conn.cursor()

            # Get old record data before update
            old_record = c.execute(f"SELECT name, surname FROM {table} WHERE rowid = ?", (id,)).fetchone()
            
            # Update the record
            c.execute(f"""
                UPDATE {table} 
                SET name = ?, surname = ?, timestamp = ?
                WHERE rowid = ?
            """, (name, surname, timestamp, id))
            conn.commit()

            # Handle QR code regeneration if requested
            if regenerate_qr and table == 'generation_records':
                # Delete old QR code if it exists
                if old_record:
                    old_qr_path = f"static/qr_codes/{old_record[0].lower()}_{old_record[1].lower()}_qr.png"
                    if os.path.exists(old_qr_path):
                        os.remove(old_qr_path)

                # Generate new QR code
                data = f"{name},{surname}"
                encrypted_data = encryptor.encrypt(data.encode()).decode()
                
                filename = f"static/qr_codes/{name.lower()}_{surname.lower()}_qr.png"
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(encrypted_data)
                qr.make(fit=True)
                img = qr.make_image(fill="black", back_color="white")
                img.save(filename)

                # If regenerating QR, stay on the edit page
                conn.close()
                return render_template('edit.html', 
                                    record=(timestamp, name, surname), 
                                    table=table,
                                    qr_updated=True)

            conn.close()
            return redirect(url_for('records'))
        except sqlite3.Error as e:
            return render_template('edit.html', error=f"Error al actualizar: {str(e)}")
    else:
        table = request.args.get('table', 'generation_records')
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute(f"SELECT * FROM {table} WHERE rowid = ?", (id,))
        record = c.fetchone()
        conn.close()
        return render_template('edit.html', record=record, table=table)

if __name__ == '__main__':
    app.run()