from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps

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


@app.route('/admin/add-product', methods=['POST'])
def add_product():
    nume = request.form['nume']
    descriere = request.form['descriere']
    pret = float(request.form['pret'])
    imagine = request.form['imagine']
    categorie = request.form['categorie']
    ingrediente = request.form['ingrediente']

    conn = get_db_connection()
    conn.execute('INSERT INTO produse (nume, descriere, pret, imagine,ingrediente, categorie) VALUES (?, ?, ?, ?, ?, ?)',
                 (nume, descriere, pret, imagine,ingrediente, categorie))
    conn.commit()
    conn.close()

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
