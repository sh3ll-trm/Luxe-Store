from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
import os
import datetime
import json
import stripe
import urllib.request
import urllib.parse

app = Flask(__name__)
app.secret_key = "ecommerce_super_secret_key_2026"
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Database Helpers ──────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT DEFAULT '',
                address TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                icon TEXT DEFAULT '📦',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT NOT NULL,
                image TEXT NOT NULL,
                category_id INTEGER,
                stock INTEGER DEFAULT 0,
                featured INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                UNIQUE(user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total REAL NOT NULL,
                status TEXT DEFAULT 'Pending',
                payment_method TEXT DEFAULT '',
                payment_id TEXT DEFAULT '',
                shipping_name TEXT,
                shipping_address TEXT,
                shipping_phone TEXT,
                coupon_code TEXT,
                discount REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS coupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_percent REAL NOT NULL,
                max_uses INTEGER DEFAULT 100,
                used INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                expires_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT DEFAULT ''
            );
        ''')

        # Seed default settings if empty
        settings_count = db.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        if settings_count == 0:
            default_settings = [
                ('stripe_enabled', '0'),
                ('stripe_publishable_key', ''),
                ('stripe_secret_key', ''),
                ('paypal_enabled', '0'),
                ('paypal_client_id', ''),
                ('paypal_client_secret', ''),
                ('paypal_mode', 'sandbox'),
                ('store_currency', 'usd'),
            ]
            db.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", default_settings)

        # Seed admin if not exists
        admin = db.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        if not admin:
            db.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                       ('admin', generate_password_hash('admin123')))

        # Seed categories if empty
        cat_count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if cat_count == 0:
            categories = [
                ('Electronics', '💻'),
                ('Clothing', '👕'),
                ('Home & Garden', '🏡'),
                ('Sports', '⚽'),
                ('Books', '📚'),
                ('Gaming', '🎮'),
            ]
            db.executemany("INSERT INTO categories (name, icon) VALUES (?, ?)", categories)

        # Seed products if empty
        prod_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if prod_count == 0:
            products = [
                ('Wireless Headphones Pro', 79.99, 'Premium noise-cancelling wireless headphones with 40-hour battery life and crystal-clear audio.', '/static/uploads/placeholder.png', 1, 50, 1),
                ('Smart Watch Ultra', 199.99, 'Advanced fitness tracking, heart rate monitor, GPS, and seamless smartphone integration.', '/static/uploads/placeholder.png', 1, 30, 1),
                ('Designer Hoodie', 49.99, 'Ultra-soft premium cotton hoodie with minimalist design. Available in multiple colors.', '/static/uploads/placeholder.png', 2, 100, 0),
                ('Running Shoes X9', 129.99, 'Lightweight performance running shoes with advanced cushioning technology.', '/static/uploads/placeholder.png', 4, 75, 1),
                ('Mechanical Keyboard RGB', 89.99, 'Cherry MX switches, per-key RGB lighting, aircraft-grade aluminum frame.', '/static/uploads/placeholder.png', 1, 40, 0),
                ('Graphic Novel Collection', 34.99, 'Bestselling graphic novel box set — includes 5 award-winning titles.', '/static/uploads/placeholder.png', 5, 60, 0),
                ('Gaming Mouse Elite', 59.99, '16000 DPI optical sensor, 8 programmable buttons, ergonomic design.', '/static/uploads/placeholder.png', 6, 45, 1),
                ('Yoga Mat Premium', 39.99, 'Non-slip eco-friendly yoga mat with alignment markers. 6mm thickness.', '/static/uploads/placeholder.png', 4, 80, 0),
                ('LED Desk Lamp', 29.99, 'Adjustable color temperature and brightness, USB charging port, touch controls.', '/static/uploads/placeholder.png', 3, 90, 0),
                ('Bluetooth Speaker Max', 69.99, '360-degree surround sound, waterproof IPX7, 24-hour battery, deep bass.', '/static/uploads/placeholder.png', 1, 55, 1),
                ('Cotton T-Shirt Pack', 24.99, 'Pack of 3 premium cotton t-shirts. Comfortable everyday wear.', '/static/uploads/placeholder.png', 2, 200, 0),
                ('Indoor Plant Set', 44.99, 'Set of 3 low-maintenance indoor plants with decorative pots.', '/static/uploads/placeholder.png', 3, 35, 0),
            ]
            db.executemany(
                "INSERT INTO products (name, price, description, image, category_id, stock, featured) VALUES (?, ?, ?, ?, ?, ?, ?)",
                products
            )

        # Seed a coupon
        coupon_count = db.execute("SELECT COUNT(*) FROM coupons").fetchone()[0]
        if coupon_count == 0:
            db.execute("INSERT INTO coupons (code, discount_percent, max_uses) VALUES (?, ?, ?)",
                       ('WELCOME10', 10, 999))
            db.execute("INSERT INTO coupons (code, discount_percent, max_uses) VALUES (?, ?, ?)",
                       ('SAVE20', 20, 50))

        db.commit()


# ── Auth Decorators ───────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_setting(key, default=''):
    """Get a setting value from the database."""
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key, value):
    """Set a setting value in the database."""
    db = get_db()
    existing = db.execute("SELECT id FROM settings WHERE key = ?", (key,)).fetchone()
    if existing:
        db.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    else:
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
    db.commit()


# ── Context Processor ─────────────────────────────────────────────

@app.context_processor
def inject_globals():
    cart_count = 0
    wishlist_count = 0
    if 'user_id' in session:
        db = get_db()
        cart_count = db.execute("SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?",
                                (session['user_id'],)).fetchone()[0]
        wishlist_count = db.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = ?",
                                   (session['user_id'],)).fetchone()[0]
    categories = get_db().execute("SELECT * FROM categories ORDER BY name").fetchall()
    return dict(cart_count=cart_count, wishlist_count=wishlist_count, all_categories=categories)


# ══════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════

# ── Home ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    featured = db.execute(
        "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.featured = 1 ORDER BY p.created_at DESC LIMIT 8"
    ).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    latest = db.execute(
        "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id ORDER BY p.created_at DESC LIMIT 4"
    ).fetchall()
    return render_template('index.html', featured=featured, categories=categories, latest=latest)


# ── Products ──────────────────────────────────────────────────────

@app.route('/products')
def products():
    db = get_db()
    category_id = request.args.get('category', type=int)
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id"
    params = []
    if category_id:
        query += " WHERE p.category_id = ?"
        params.append(category_id)

    if sort == 'price_low':
        query += " ORDER BY p.price ASC"
    elif sort == 'price_high':
        query += " ORDER BY p.price DESC"
    elif sort == 'name':
        query += " ORDER BY p.name ASC"
    else:
        query += " ORDER BY p.created_at DESC"

    # Count total
    count_query = query.replace("SELECT p.*, c.name as category_name", "SELECT COUNT(*)")
    total = db.execute(count_query, params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)

    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    items = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    active_category = None
    if category_id:
        active_category = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    return render_template('products.html', products=items, categories=categories,
                           active_category=active_category, sort=sort,
                           page=page, total_pages=total_pages)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    db = get_db()
    product = db.execute(
        "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?",
        (product_id,)
    ).fetchone()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))

    reviews = db.execute(
        "SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.product_id = ? AND r.approved = 1 ORDER BY r.created_at DESC",
        (product_id,)
    ).fetchall()

    avg_rating = db.execute(
        "SELECT AVG(rating) FROM reviews WHERE product_id = ? AND approved = 1", (product_id,)
    ).fetchone()[0] or 0

    related = db.execute(
        "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.category_id = ? AND p.id != ? LIMIT 4",
        (product['category_id'], product_id)
    ).fetchall()

    in_wishlist = False
    if 'user_id' in session:
        in_wishlist = db.execute(
            "SELECT 1 FROM wishlist WHERE user_id = ? AND product_id = ?",
            (session['user_id'], product_id)
        ).fetchone() is not None

    return render_template('product_detail.html', product=product, reviews=reviews,
                           avg_rating=avg_rating, related=related, in_wishlist=in_wishlist)


# ── Search ────────────────────────────────────────────────────────

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    db = get_db()
    if q:
        results = db.execute(
            "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.name LIKE ? OR p.description LIKE ? ORDER BY p.name",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
    else:
        results = []
    return render_template('search_results.html', results=results, query=q)


@app.route('/api/search-suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    db = get_db()
    results = db.execute("SELECT id, name, price FROM products WHERE name LIKE ? LIMIT 5", (f'%{q}%',)).fetchall()
    return jsonify([dict(r) for r in results])


# ── Auth ──────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            db = get_db()
            try:
                db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                           (username, email, generate_password_hash(password)))
                db.commit()
                flash('Account created! Please log in.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Username or email already exists.', 'error')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            if user['is_banned']:
                flash('Your account has been banned.', 'error')
            else:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        address = request.form.get('address', '')
        phone = request.form.get('phone', '')
        try:
            db.execute("UPDATE users SET full_name = ?, email = ?, address = ?, phone = ? WHERE id = ?",
                       (full_name, email, address, phone, session['user_id']))
            db.commit()
            flash('Profile updated!', 'success')
        except sqlite3.IntegrityError:
            flash('Email already in use.', 'error')
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    orders = db.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                        (session['user_id'],)).fetchall()
    return render_template('profile.html', user=user, orders=orders)


# ── Cart ──────────────────────────────────────────────────────────

@app.route('/cart')
@login_required
def cart():
    db = get_db()
    items = db.execute(
        "SELECT ci.*, p.name, p.price, p.image, p.stock FROM cart_items ci JOIN products p ON ci.product_id = p.id WHERE ci.user_id = ?",
        (session['user_id'],)
    ).fetchall()
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    return render_template('cart.html', items=items, subtotal=subtotal)


@app.route('/cart/add', methods=['POST'])
@login_required
def cart_add():
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)
    db = get_db()

    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))

    existing = db.execute("SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
                          (session['user_id'], product_id)).fetchone()
    if existing:
        db.execute("UPDATE cart_items SET quantity = quantity + ? WHERE id = ?", (quantity, existing['id']))
    else:
        db.execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                   (session['user_id'], product_id, quantity))
    db.commit()
    flash(f'{product["name"]} added to cart!', 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_count = db.execute("SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?",
                                (session['user_id'],)).fetchone()[0]
        return jsonify({'success': True, 'cart_count': cart_count})

    return redirect(request.referrer or url_for('products'))


@app.route('/cart/update', methods=['POST'])
@login_required
def cart_update():
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)
    db = get_db()
    if quantity <= 0:
        db.execute("DELETE FROM cart_items WHERE id = ? AND user_id = ?", (item_id, session['user_id']))
    else:
        db.execute("UPDATE cart_items SET quantity = ? WHERE id = ? AND user_id = ?",
                   (quantity, item_id, session['user_id']))
    db.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        items = db.execute(
            "SELECT ci.*, p.price FROM cart_items ci JOIN products p ON ci.product_id = p.id WHERE ci.user_id = ?",
            (session['user_id'],)
        ).fetchall()
        subtotal = sum(i['price'] * i['quantity'] for i in items)
        cart_count = sum(i['quantity'] for i in items)
        return jsonify({'success': True, 'subtotal': subtotal, 'cart_count': cart_count})

    return redirect(url_for('cart'))


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def cart_remove(item_id):
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE id = ? AND user_id = ?", (item_id, session['user_id']))
    db.commit()
    flash('Item removed from cart.', 'info')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_count = db.execute("SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?",
                                (session['user_id'],)).fetchone()[0]
        return jsonify({'success': True, 'cart_count': cart_count})

    return redirect(url_for('cart'))


# ── Wishlist ──────────────────────────────────────────────────────

@app.route('/wishlist')
@login_required
def wishlist():
    db = get_db()
    items = db.execute(
        "SELECT w.id as wishlist_id, p.* FROM wishlist w JOIN products p ON w.product_id = p.id WHERE w.user_id = ?",
        (session['user_id'],)
    ).fetchall()
    return render_template('wishlist.html', items=items)


@app.route('/wishlist/toggle', methods=['POST'])
@login_required
def wishlist_toggle():
    product_id = request.form.get('product_id', type=int)
    db = get_db()
    existing = db.execute("SELECT * FROM wishlist WHERE user_id = ? AND product_id = ?",
                          (session['user_id'], product_id)).fetchone()
    if existing:
        db.execute("DELETE FROM wishlist WHERE id = ?", (existing['id'],))
        action = 'removed'
    else:
        db.execute("INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)",
                   (session['user_id'], product_id))
        action = 'added'
    db.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        wishlist_count = db.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = ?",
                                   (session['user_id'],)).fetchone()[0]
        return jsonify({'success': True, 'action': action, 'wishlist_count': wishlist_count})

    flash(f'Product {action} to wishlist.', 'success')
    return redirect(request.referrer or url_for('products'))


# ── Checkout & Orders ─────────────────────────────────────────────

def _create_order(db, user_id, items, shipping_name, shipping_address, shipping_phone, coupon_code, discount, total, payment_method='', payment_id=''):
    """Helper to create an order and its items, clear cart, and return order_id."""
    order_id = db.execute(
        "INSERT INTO orders (user_id, total, shipping_name, shipping_address, shipping_phone, coupon_code, discount, payment_method, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, total, shipping_name, shipping_address, shipping_phone, coupon_code, discount, payment_method, payment_id)
    ).lastrowid

    for item in items:
        db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                   (order_id, item['product_id'], item['quantity'], item['price']))
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                   (item['quantity'], item['product_id'], item['quantity']))

    db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    db.commit()
    return order_id


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    db = get_db()
    items = db.execute(
        "SELECT ci.*, p.name, p.price, p.image, p.stock FROM cart_items ci JOIN products p ON ci.product_id = p.id WHERE ci.user_id = ?",
        (session['user_id'],)
    ).fetchall()
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))

    subtotal = sum(item['price'] * item['quantity'] for item in items)
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    stripe_enabled = get_setting('stripe_enabled') == '1' and get_setting('stripe_publishable_key')
    paypal_enabled = get_setting('paypal_enabled') == '1' and get_setting('paypal_client_id')

    if request.method == 'POST':
        shipping_name = request.form.get('shipping_name', '')
        shipping_address = request.form.get('shipping_address', '')
        shipping_phone = request.form.get('shipping_phone', '')
        coupon_code = request.form.get('coupon_code', '').strip().upper()
        payment_method = request.form.get('payment_method', 'none')

        discount = 0
        if coupon_code:
            coupon = db.execute(
                "SELECT * FROM coupons WHERE code = ? AND active = 1 AND used < max_uses",
                (coupon_code,)
            ).fetchone()
            if coupon:
                if coupon['expires_at'] and coupon['expires_at'] < datetime.datetime.now().isoformat():
                    flash('Coupon has expired.', 'error')
                    return render_template('checkout.html', items=items, subtotal=subtotal, user=user,
                                           stripe_enabled=stripe_enabled, paypal_enabled=paypal_enabled)
                discount = coupon['discount_percent']
                db.execute("UPDATE coupons SET used = used + 1 WHERE id = ?", (coupon['id'],))
            else:
                flash('Invalid or expired coupon.', 'error')
                return render_template('checkout.html', items=items, subtotal=subtotal, user=user,
                                       stripe_enabled=stripe_enabled, paypal_enabled=paypal_enabled)

        total = subtotal * (1 - discount / 100)

        # Store checkout data in session for payment processing
        session['checkout_data'] = {
            'shipping_name': shipping_name,
            'shipping_address': shipping_address,
            'shipping_phone': shipping_phone,
            'coupon_code': coupon_code,
            'discount': discount,
            'total': total,
            'subtotal': subtotal,
        }

        # ── Stripe Payment ──
        if payment_method == 'stripe' and stripe_enabled:
            try:
                stripe.api_key = get_setting('stripe_secret_key')
                currency = get_setting('store_currency', 'usd')

                line_items = []
                for item in items:
                    line_items.append({
                        'price_data': {
                            'currency': currency,
                            'product_data': {'name': item['name']},
                            'unit_amount': int(item['price'] * 100),
                        },
                        'quantity': item['quantity'],
                    })

                # Apply discount as a coupon in Stripe if applicable
                discounts = []
                if discount > 0:
                    stripe_coupon = stripe.Coupon.create(
                        percent_off=discount,
                        duration='once',
                    )
                    discounts = [{'coupon': stripe_coupon.id}]

                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=line_items,
                    mode='payment',
                    discounts=discounts,
                    success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=url_for('payment_cancel', _external=True),
                    customer_email=db.execute("SELECT email FROM users WHERE id = ?", (session['user_id'],)).fetchone()['email'],
                )
                session['stripe_session_id'] = checkout_session.id
                return redirect(checkout_session.url)
            except Exception as e:
                flash(f'Stripe error: {str(e)}', 'error')
                return render_template('checkout.html', items=items, subtotal=subtotal, user=user,
                                       stripe_enabled=stripe_enabled, paypal_enabled=paypal_enabled)

        # ── PayPal Payment ──
        elif payment_method == 'paypal' and paypal_enabled:
            # Redirect to payment page with PayPal buttons
            return render_template('payment_paypal.html',
                                   total=total, items=items,
                                   paypal_client_id=get_setting('paypal_client_id'),
                                   paypal_mode=get_setting('paypal_mode', 'sandbox'),
                                   currency=get_setting('store_currency', 'usd').upper())

        # ── No Payment (Manual / No gateway configured) ──
        else:
            order_id = _create_order(db, session['user_id'], items,
                                     shipping_name, shipping_address, shipping_phone,
                                     coupon_code, discount, total, 'manual', '')
            session.pop('checkout_data', None)
            flash(f'Order #{order_id} placed successfully!', 'success')
            return redirect(url_for('orders'))

    return render_template('checkout.html', items=items, subtotal=subtotal, user=user,
                           stripe_enabled=stripe_enabled, paypal_enabled=paypal_enabled)


# ── Stripe Success/Cancel ─────────────────────────────────────────

@app.route('/payment/success')
@login_required
def payment_success():
    stripe_session_id = request.args.get('session_id', '')
    checkout_data = session.pop('checkout_data', None)

    if not checkout_data:
        flash('Payment session expired.', 'error')
        return redirect(url_for('cart'))

    db = get_db()
    items = db.execute(
        "SELECT ci.*, p.name, p.price, p.image, p.stock FROM cart_items ci JOIN products p ON ci.product_id = p.id WHERE ci.user_id = ?",
        (session['user_id'],)
    ).fetchall()

    if not items:
        flash('Cart is empty.', 'warning')
        return redirect(url_for('orders'))

    # Verify Stripe payment
    payment_id = stripe_session_id
    if stripe_session_id:
        try:
            stripe.api_key = get_setting('stripe_secret_key')
            sess = stripe.checkout.Session.retrieve(stripe_session_id)
            if sess.payment_status != 'paid':
                flash('Payment not completed.', 'error')
                return redirect(url_for('cart'))
            payment_id = sess.payment_intent
        except Exception:
            pass

    order_id = _create_order(db, session['user_id'], items,
                             checkout_data['shipping_name'], checkout_data['shipping_address'],
                             checkout_data['shipping_phone'], checkout_data['coupon_code'],
                             checkout_data['discount'], checkout_data['total'],
                             'stripe', payment_id)

    session.pop('stripe_session_id', None)
    flash(f'Payment successful! Order #{order_id} placed.', 'success')
    return redirect(url_for('orders'))


@app.route('/payment/cancel')
@login_required
def payment_cancel():
    session.pop('checkout_data', None)
    session.pop('stripe_session_id', None)
    flash('Payment was cancelled.', 'warning')
    return redirect(url_for('checkout'))


# ── PayPal API Routes ─────────────────────────────────────────────

@app.route('/api/paypal/create-order', methods=['POST'])
@login_required
def paypal_create_order():
    checkout_data = session.get('checkout_data')
    if not checkout_data:
        return jsonify({'error': 'No checkout data'}), 400

    client_id = get_setting('paypal_client_id')
    client_secret = get_setting('paypal_client_secret')
    mode = get_setting('paypal_mode', 'sandbox')
    currency = get_setting('store_currency', 'usd').upper()

    base_url = 'https://api-m.sandbox.paypal.com' if mode == 'sandbox' else 'https://api-m.paypal.com'

    try:
        # Get access token
        auth_data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode()
        auth_req = urllib.request.Request(f'{base_url}/v1/oauth2/token', data=auth_data)
        auth_req.add_header('Accept', 'application/json')
        auth_req.add_header('Accept-Language', 'en_US')
        credentials = f"{client_id}:{client_secret}"
        import base64
        auth_req.add_header('Authorization', 'Basic ' + base64.b64encode(credentials.encode()).decode())

        with urllib.request.urlopen(auth_req) as resp:
            token_data = json.loads(resp.read())
        access_token = token_data['access_token']

        # Create order
        order_data = json.dumps({
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': currency,
                    'value': f"{checkout_data['total']:.2f}"
                }
            }]
        }).encode()

        order_req = urllib.request.Request(f'{base_url}/v2/checkout/orders', data=order_data)
        order_req.add_header('Content-Type', 'application/json')
        order_req.add_header('Authorization', f'Bearer {access_token}')

        with urllib.request.urlopen(order_req) as resp:
            order_result = json.loads(resp.read())

        return jsonify({'id': order_result['id']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/paypal/capture-order', methods=['POST'])
@login_required
def paypal_capture_order():
    data = request.json
    paypal_order_id = data.get('orderID', '')
    checkout_data = session.pop('checkout_data', None)

    if not checkout_data:
        return jsonify({'error': 'No checkout data'}), 400

    client_id = get_setting('paypal_client_id')
    client_secret = get_setting('paypal_client_secret')
    mode = get_setting('paypal_mode', 'sandbox')

    base_url = 'https://api-m.sandbox.paypal.com' if mode == 'sandbox' else 'https://api-m.paypal.com'

    try:
        # Get access token
        auth_data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode()
        auth_req = urllib.request.Request(f'{base_url}/v1/oauth2/token', data=auth_data)
        auth_req.add_header('Accept', 'application/json')
        credentials = f"{client_id}:{client_secret}"
        import base64
        auth_req.add_header('Authorization', 'Basic ' + base64.b64encode(credentials.encode()).decode())

        with urllib.request.urlopen(auth_req) as resp:
            token_data = json.loads(resp.read())
        access_token = token_data['access_token']

        # Capture payment
        capture_req = urllib.request.Request(f'{base_url}/v2/checkout/orders/{paypal_order_id}/capture', data=b'')
        capture_req.add_header('Content-Type', 'application/json')
        capture_req.add_header('Authorization', f'Bearer {access_token}')

        with urllib.request.urlopen(capture_req) as resp:
            capture_result = json.loads(resp.read())

        if capture_result.get('status') == 'COMPLETED':
            db = get_db()
            items = db.execute(
                "SELECT ci.*, p.name, p.price, p.image, p.stock FROM cart_items ci JOIN products p ON ci.product_id = p.id WHERE ci.user_id = ?",
                (session['user_id'],)
            ).fetchall()

            if items:
                order_id = _create_order(db, session['user_id'], items,
                                         checkout_data['shipping_name'], checkout_data['shipping_address'],
                                         checkout_data['shipping_phone'], checkout_data['coupon_code'],
                                         checkout_data['discount'], checkout_data['total'],
                                         'paypal', paypal_order_id)
                return jsonify({'success': True, 'order_id': order_id})
            else:
                return jsonify({'error': 'Cart is empty'}), 400
        else:
            return jsonify({'error': 'Payment not completed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/orders')
@login_required
def orders():
    db = get_db()
    user_orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (session['user_id'],)
    ).fetchall()

    orders_with_items = []
    for order in user_orders:
        items = db.execute(
            "SELECT oi.*, p.name, p.image FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
            (order['id'],)
        ).fetchall()
        orders_with_items.append({'order': order, 'items': items})

    return render_template('orders.html', orders=orders_with_items)


# ── Reviews ───────────────────────────────────────────────────────

@app.route('/review/add', methods=['POST'])
@login_required
def add_review():
    product_id = request.form.get('product_id', type=int)
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please select a valid rating.', 'error')
        return redirect(url_for('product_detail', product_id=product_id))

    db = get_db()
    existing = db.execute("SELECT * FROM reviews WHERE user_id = ? AND product_id = ?",
                          (session['user_id'], product_id)).fetchone()
    if existing:
        flash('You already reviewed this product.', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))

    db.execute("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (?, ?, ?, ?)",
               (session['user_id'], product_id, rating, comment))
    db.commit()
    flash('Review submitted for moderation!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))


# ── Apply Coupon (AJAX) ──────────────────────────────────────────

@app.route('/api/apply-coupon', methods=['POST'])
@login_required
def apply_coupon():
    code = request.json.get('code', '').strip().upper()
    db = get_db()
    coupon = db.execute(
        "SELECT * FROM coupons WHERE code = ? AND active = 1 AND used < max_uses",
        (code,)
    ).fetchone()
    if coupon:
        if coupon['expires_at'] and coupon['expires_at'] < datetime.datetime.now().isoformat():
            return jsonify({'success': False, 'message': 'Coupon has expired.'})
        return jsonify({'success': True, 'discount': coupon['discount_percent']})
    return jsonify({'success': False, 'message': 'Invalid or expired coupon.'})


# ══════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin['password_hash'], password):
            session['is_admin'] = True
            session['admin_username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'total_products': db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        'total_users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_orders': db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        'total_revenue': db.execute("SELECT COALESCE(SUM(total), 0) FROM orders").fetchone()[0],
        'pending_orders': db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0],
        'pending_reviews': db.execute("SELECT COUNT(*) FROM reviews WHERE approved = 0").fetchone()[0],
    }
    recent_orders = db.execute(
        "SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC LIMIT 10"
    ).fetchall()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)


# ── Admin Products ────────────────────────────────────────────────

@app.route('/admin/products')
@admin_required
def admin_products():
    db = get_db()
    products = db.execute(
        "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id ORDER BY p.created_at DESC"
    ).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template('admin/products.html', products=products, categories=categories)


@app.route('/admin/products/add', methods=['POST'])
@admin_required
def admin_add_product():
    name = request.form.get('name', '').strip()
    price = request.form.get('price', type=float)
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', type=int)
    stock = request.form.get('stock', 0, type=int)
    featured = 1 if request.form.get('featured') else 0

    image_path = '/static/uploads/placeholder.png'
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = f'/static/uploads/{filename}'

    if name and price is not None and description:
        db = get_db()
        db.execute(
            "INSERT INTO products (name, price, description, image, category_id, stock, featured) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, price, description, image_path, category_id, stock, featured)
        )
        db.commit()
        flash('Product added!', 'success')
    else:
        flash('Name, price, and description are required.', 'error')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/edit/<int:product_id>', methods=['POST'])
@admin_required
def admin_edit_product(product_id):
    name = request.form.get('name', '').strip()
    price = request.form.get('price', type=float)
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', type=int)
    stock = request.form.get('stock', 0, type=int)
    featured = 1 if request.form.get('featured') else 0

    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin_products'))

    image_path = product['image']
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{filename}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = f'/static/uploads/{filename}'

    if name and price is not None and description:
        db.execute(
            "UPDATE products SET name = ?, price = ?, description = ?, image = ?, category_id = ?, stock = ?, featured = ? WHERE id = ?",
            (name, price, description, image_path, category_id, stock, featured, product_id)
        )
        db.commit()
        flash('Product updated!', 'success')
    else:
        flash('All fields are required.', 'error')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin_products'))


# ── Admin Categories ──────────────────────────────────────────────

@app.route('/admin/categories')
@admin_required
def admin_categories():
    db = get_db()
    categories = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM products WHERE category_id = c.id) as product_count FROM categories c ORDER BY c.name"
    ).fetchall()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', '📦').strip()
    if name:
        db = get_db()
        try:
            db.execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (name, icon))
            db.commit()
            flash('Category added!', 'success')
        except sqlite3.IntegrityError:
            flash('Category already exists.', 'error')
    else:
        flash('Category name is required.', 'error')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/edit/<int:cat_id>', methods=['POST'])
@admin_required
def admin_edit_category(cat_id):
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', '📦').strip()
    if name:
        db = get_db()
        try:
            db.execute("UPDATE categories SET name = ?, icon = ? WHERE id = ?", (name, icon, cat_id))
            db.commit()
            flash('Category updated!', 'success')
        except sqlite3.IntegrityError:
            flash('Category name already exists.', 'error')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def admin_delete_category(cat_id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    db.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin_categories'))


# ── Admin Orders ──────────────────────────────────────────────────

@app.route('/admin/orders')
@admin_required
def admin_orders():
    db = get_db()
    status_filter = request.args.get('status', '')
    query = "SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id"
    params = []
    if status_filter:
        query += " WHERE o.status = ?"
        params.append(status_filter)
    query += " ORDER BY o.created_at DESC"
    all_orders = db.execute(query, params).fetchall()

    orders_with_items = []
    for order in all_orders:
        items = db.execute(
            "SELECT oi.*, p.name, p.image FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
            (order['id'],)
        ).fetchall()
        orders_with_items.append({'order': order, 'items': items})

    return render_template('admin/orders.html', orders=orders_with_items, status_filter=status_filter)


@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
@admin_required
def admin_update_order(order_id):
    status = request.form.get('status', '')
    if status in ('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'):
        db = get_db()
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        db.commit()
        flash(f'Order #{order_id} status updated to {status}.', 'success')
    return redirect(url_for('admin_orders'))


# ── Admin Users ───────────────────────────────────────────────────

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as order_count FROM users u ORDER BY u.created_at DESC"
    ).fetchall()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/toggle-ban/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_ban(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_banned'] else 1
        db.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_status, user_id))
        db.commit()
        action = 'banned' if new_status else 'unbanned'
        flash(f'User {user["username"]} {action}.', 'success')
    return redirect(url_for('admin_users'))


# ── Admin Coupons ─────────────────────────────────────────────────

@app.route('/admin/coupons')
@admin_required
def admin_coupons():
    db = get_db()
    coupons = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return render_template('admin/coupons.html', coupons=coupons)


@app.route('/admin/coupons/add', methods=['POST'])
@admin_required
def admin_add_coupon():
    code = request.form.get('code', '').strip().upper()
    discount = request.form.get('discount_percent', type=float)
    max_uses = request.form.get('max_uses', 100, type=int)
    expires_at = request.form.get('expires_at', '')

    if code and discount:
        db = get_db()
        try:
            db.execute("INSERT INTO coupons (code, discount_percent, max_uses, expires_at) VALUES (?, ?, ?, ?)",
                       (code, discount, max_uses, expires_at or None))
            db.commit()
            flash('Coupon created!', 'success')
        except sqlite3.IntegrityError:
            flash('Coupon code already exists.', 'error')
    else:
        flash('Code and discount are required.', 'error')
    return redirect(url_for('admin_coupons'))


@app.route('/admin/coupons/toggle/<int:coupon_id>', methods=['POST'])
@admin_required
def admin_toggle_coupon(coupon_id):
    db = get_db()
    coupon = db.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,)).fetchone()
    if coupon:
        db.execute("UPDATE coupons SET active = ? WHERE id = ?", (0 if coupon['active'] else 1, coupon_id))
        db.commit()
    return redirect(url_for('admin_coupons'))


@app.route('/admin/coupons/delete/<int:coupon_id>', methods=['POST'])
@admin_required
def admin_delete_coupon(coupon_id):
    db = get_db()
    db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
    db.commit()
    flash('Coupon deleted.', 'success')
    return redirect(url_for('admin_coupons'))


# ── Admin Reviews ─────────────────────────────────────────────────

@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    db = get_db()
    reviews = db.execute(
        "SELECT r.*, u.username, p.name as product_name FROM reviews r JOIN users u ON r.user_id = u.id JOIN products p ON r.product_id = p.id ORDER BY r.approved ASC, r.created_at DESC"
    ).fetchall()
    return render_template('admin/reviews.html', reviews=reviews)


@app.route('/admin/reviews/approve/<int:review_id>', methods=['POST'])
@admin_required
def admin_approve_review(review_id):
    db = get_db()
    db.execute("UPDATE reviews SET approved = 1 WHERE id = ?", (review_id,))
    db.commit()
    flash('Review approved.', 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/reviews/delete/<int:review_id>', methods=['POST'])
@admin_required
def admin_delete_review(review_id):
    db = get_db()
    db.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    db.commit()
    flash('Review deleted.', 'success')
    return redirect(url_for('admin_reviews'))


# ── Admin Analytics ───────────────────────────────────────────────

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    db = get_db()
    # Revenue by day (last 30 days)
    revenue_data = db.execute(
        "SELECT DATE(created_at) as day, SUM(total) as revenue, COUNT(*) as orders FROM orders WHERE created_at >= DATE('now', '-30 days') GROUP BY DATE(created_at) ORDER BY day"
    ).fetchall()

    # Top products by quantity sold
    top_products = db.execute(
        "SELECT p.name, SUM(oi.quantity) as total_sold, SUM(oi.quantity * oi.price) as total_revenue FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_sold DESC LIMIT 10"
    ).fetchall()

    # Orders by status
    order_stats = db.execute(
        "SELECT status, COUNT(*) as count FROM orders GROUP BY status"
    ).fetchall()

    return render_template('admin/analytics.html',
                           revenue_data=[dict(r) for r in revenue_data],
                           top_products=[dict(r) for r in top_products],
                           order_stats=[dict(r) for r in order_stats])


# ── Admin Settings (Payment Configuration) ───────────────────────

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        keys = [
            'stripe_enabled', 'stripe_publishable_key', 'stripe_secret_key',
            'paypal_enabled', 'paypal_client_id', 'paypal_client_secret', 'paypal_mode',
            'store_currency',
        ]
        for key in keys:
            if key in ('stripe_enabled', 'paypal_enabled'):
                val = '1' if request.form.get(key) else '0'
            else:
                val = request.form.get(key, '').strip()
            set_setting(key, val)
        flash('Settings saved!', 'success')
        return redirect(url_for('admin_settings'))

    settings = {}
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    for row in rows:
        settings[row['key']] = row['value']
    return render_template('admin/settings.html', settings=settings)


# ══════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
