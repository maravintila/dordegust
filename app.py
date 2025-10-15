from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
from functools import wraps
import os
import time
import uuid
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras


app = Flask(__name__)
app.secret_key = '1234'

cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Alege folderul în funcție de mediu: pe mac/dev folosim folder în proiect, pe server Linux folosește /var/www/...
if os.getenv('FLASK_ENV') == 'production':
    UPLOAD_FOLDER = '/var/www/dordegust/uploads'
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    # sslmode=require e recomandat pe Render
    conn = psycopg2.connect(database_url, sslmode='require')
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Homepage
@app.route('/')
def index():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM produse LIMIT 3')
            produse_populare = cur.fetchall()
    return render_template('index.html', produse_populare=produse_populare)

@app.route('/products')
def products():
    category = request.args.get('category')
    search = request.args.get('search')


    base_query = 'SELECT * FROM produse WHERE 1=1'
    params = []
    if category:
        base_query += ' AND categorie = %s'
        params.append(category)
    if search:
        base_query += ' AND nume ILIKE %s'
        params.append(f"%{search}%")


    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT DISTINCT categorie FROM produse')
            categories = cur.fetchall()
            cur.execute(base_query, params)
            produse = cur.fetchall()


    return render_template('products.html', produse=produse, categories=categories)

# Pagina de contact
@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/products/<int:product_id>')
def product_details(product_id):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM produse WHERE id = %s', (product_id,))
            produs = cur.fetchone()
    return render_template('product.html', produs=produs)

@app.route('/admin', methods=['GET'])
@login_required
def admin():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM produse')
            produse = cur.fetchall()
            cur.execute('SELECT DISTINCT categorie FROM produse')
            categories = cur.fetchall()
        return render_template('admin.html', produse=produse, categories=categories)


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
    alergeni = request.form.get('alergeni')
    image_file = request.files.get('imagine')
    image_url = None

    if image_file and allowed_file(image_file.filename):
        # urcă direct în Cloudinary
        upload_result = cloudinary.uploader.upload(image_file)
        image_url = upload_result.get("secure_url")



    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
            INSERT INTO produse (nume, descriere, pret, imagine, ingrediente, categorie, alergeni)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (nume, descriere, pret, image_url, ingrediente, categorie, alergeni))

        conn.commit()


    flash('Produs adăugat cu succes!')
    return redirect(url_for('admin'))

# Credențiale de test
USERNAME = os.getenv("ADMIN_USERNAME")
PASSWORD = os.getenv("ADMIN_PASSWORD")

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
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM produse')
            produse = cur.fetchall()
            cur.execute('SELECT DISTINCT categorie FROM produse')
            categories = cur.fetchall()
    return render_template('edit_products.html', produse=produse, categories=categories)



@app.route('/admin/edit-product/<int:product_id>', methods=['GET'])
@login_required
def edit_product(product_id):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM produse WHERE id = %s', (product_id,))
            produs = cur.fetchall()
            cur.execute('SELECT DISTINCT categorie FROM produse')
            categories = cur.fetchall()
    return render_template('edit.html', produs=produs, categories=categories)


@app.route('/admin/update-product/<int:pid>', methods=['POST'])
@login_required
def update_product(pid):
    # Suport atât JSON vechi cât și form-data nou
    if request.content_type and 'multipart/form-data' in request.content_type:
        form = request.form
        file = request.files.get('imagine')
        nume = form.get('nume')
        descriere = form.get('descriere')
        pret = form.get('pret')
        ingrediente = form.get('ingrediente')
        categorie = form.get('categorie')
        alergeni = form.get('alergeni')
        new_image_url = None

        # Dacă s-a ales o imagine nouă → urcă în Cloudinary
        if file and file.filename:
            upload = cloudinary.uploader.upload(
                file,
                folder="dordegust/products"
            )
            new_image_url = upload["secure_url"]

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if new_image_url:
                    cur.execute("""
                        UPDATE produse
                        SET nume=%s, descriere=%s, pret=%s, ingrediente=%s, categorie=%s, alergeni=%s, imagine=%s
                        WHERE id=%s
                    """, (nume, descriere, pret, ingrediente, categorie,alergeni, new_image_url, pid))
                else:
                    cur.execute("""
                        UPDATE produse
                        SET nume=%s, descriere=%s, pret=%s, ingrediente=%s, categorie=%s, alergeni=%s
                        WHERE id=%s
                    """, (nume, descriere, pret, ingrediente, categorie,alergeni, pid))
            conn.commit()

        # Răspundem cu noul URL (dacă există) ca să putem actualiza tabelul la frontend
        return {"ok": True, "image": new_image_url}, 200

    # fallback: comportamentul vechi pe JSON (dacă încă mai trimiți JSON)
    data = request.get_json(force=True)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE produse
                SET nume=%s, descriere=%s, pret=%s, imagine=%s, ingrediente=%s, categorie=%s
                WHERE id=%s
            """, (data["nume"], data["descriere"], data["pret"], data["imagine"],
                  data["ingrediente"], data["categorie"], pid))
        conn.commit()
    return {"ok": True}, 200

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return app.send_static_file('sitemap.xml')


if __name__ == "__main__":
    app.run(debug=True)
