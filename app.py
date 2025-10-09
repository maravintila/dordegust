from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
from functools import wraps
import os
import time
import uuid
from werkzeug.utils import secure_filename

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
DATABASE = 'database.db'
app.secret_key = '1234'  # Schimbă cu o cheie unică și sigură

# --- configurație uploads ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Alege folderul în funcție de mediu: pe mac/dev folosim folder în proiect, pe server Linux folosește /var/www/...
if os.getenv('FLASK_ENV') == 'production':
    UPLOAD_FOLDER = '/var/www/dordegust/uploads'
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')  # dev local (mac)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB


# Conectare la baza de date
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Homepage
@app.route('/')
def index():
    conn = get_db_connection()
    produse_populare = conn.execute('SELECT * FROM produse LIMIT 3').fetchall()
    conn.close()
    return render_template('index.html', produse_populare=produse_populare)

@app.route('/products')
def products():
    category = request.args.get('category')
    search = request.args.get('search')

    query = 'SELECT * FROM produse WHERE 1=1'
    params = []

    if category:
        query += ' AND categorie = ?'
        params.append(category)
    if search:
        query += ' AND nume LIKE ?'
        params.append(f'%{search}%')

    conn = get_db_connection()

    # Obține categoriile distincte
    categories = conn.execute('SELECT DISTINCT categorie FROM produse').fetchall()

    produse = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('products.html', produse=produse, categories=categories)


# Pagina de contact
@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/products/<int:product_id>')
def product_details(product_id):
    conn = get_db_connection()
    produs = conn.execute('SELECT * FROM produse WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return render_template('product.html', produs=produs)

@app.route('/admin', methods=['GET'])
@login_required
def admin():
    conn = get_db_connection()
    categories = conn.execute('SELECT DISTINCT categorie FROM produse').fetchall()
    conn.close()
    return render_template('admin.html', categories=categories)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # creează folderul dacă nu există

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Serve images (doar pentru dev). În producție configurează Nginx să servească /uploads/
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

# Handler pentru add-product (form multipart/form-data)
@app.route('/admin/add-product', methods=['POST'])
@login_required  # păstrează decoratorul tău de autentificare dacă există
def add_product():
    # Obține câmpurile text (form)
    nume = request.form.get('nume')
    descriere = request.form.get('descriere')
    pret = request.form.get('pret')
    ingrediente = request.form.get('ingrediente')
    categorie = request.form.get('categorie')

    # Verifică imaginea în files
    image_file = request.files.get('imagine')
    image_filename = None

    if image_file and image_file.filename != '':
        if not allowed_file(image_file.filename):
            flash('Tipul fișierului nu este permis')
            return redirect(request.referrer or url_for('admin'))

        original = secure_filename(image_file.filename)
        name, ext = os.path.splitext(original)
        # folosește uuid pentru unicitate
        new_filename = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        image_file.save(save_path)
        image_filename = new_filename

    # Dacă vrei, poți valida că nume/pret sunt setate; ex:
    if not nume or not pret:
        flash('Nume și preț sunt obligatorii')
        return redirect(request.referrer or url_for('admin'))

    # INSERT în DB - adaptează la schema ta
    try:
        conn = get_db_connection()  # înlocuiește cu funcția ta
        conn.execute('''
            INSERT INTO produse (nume, descriere, pret, imagine, ingrediente, categorie)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nume, descriere, pret, image_filename, ingrediente, categorie))
        conn.commit()
        conn.close()
    except Exception as e:
        # dacă DB eșuează șterge fișierul salvat pentru curățenie
        if image_filename:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            except Exception:
                pass
        flash(f'Eroare la salvarea în baza de date: {e}')
        return redirect(request.referrer or url_for('admin'))

    flash('Produs adăugat cu succes!')
    return redirect(url_for('admin'))

# Credențiale de test (ar trebui să fie în baza de date în realitate)
USERNAME = 'admin'
PASSWORD = 'parola123'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', message="Utilizator sau parolă greșită.")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin/edit-products', methods=['GET'])
@login_required
def edit_products():
    conn = get_db_connection()
    produse = conn.execute('SELECT * FROM produse').fetchall()
    categories = conn.execute('SELECT DISTINCT categorie FROM produse').fetchall()
    conn.close()
    return render_template('edit_products.html', produse=produse, categories=categories)



@app.route('/admin/edit-product/<int:product_id>', methods=['GET'])
@login_required
def edit_product(product_id):
    # Obține conexiunea cu baza de date
    conn = get_db_connection()

    # Preia detaliile produsului cu ID-ul specificat
    produs = conn.execute('SELECT * FROM produse WHERE id = ?', (product_id,)).fetchone()

    # Preia categoriile disponibile
    categories = conn.execute('SELECT DISTINCT categorie FROM produse').fetchall()
    conn.close()

    # Dacă produsul nu există, returnăm un mesaj de eroare
    if produs is None:
        return "Produsul nu a fost găsit.", 404

    # Randăm șablonul de editare cu detaliile produsului
    return render_template('edit.html', produs=produs, categories=categories)


@app.route('/admin/update-product/<int:product_id>', methods=['POST'])
@login_required
def update_product(product_id):
    data = request.get_json()
    nume = data.get('nume')
    descriere = data.get('descriere')
    pret = float(data.get('pret'))
    imagine = data.get('imagine')
    ingrediente = data.get('ingrediente')
    categorie = data.get('categorie')

    conn = get_db_connection()
    conn.execute(
        'UPDATE produse SET nume = ?, descriere = ?, pret = ?, imagine = ?,ingrediente = ?, categorie = ? WHERE id = ?',
        (nume, descriere, pret, imagine,ingrediente, categorie, product_id)
    )
    conn.commit()
    conn.close()

    return {'message': 'Produs actualizat cu succes!'}







if __name__ == "__main__":
    app.run(debug=True)
