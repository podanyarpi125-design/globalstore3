# app.py
import os
import json
import requests
import traceback
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

from models import db, User, Product, Purchase, Transaction
from admin_routes import admin_bp
from app_routes import app_bp
from email_utils import send_purchase_email

load_dotenv()

# ============================================================
# POSTGRESQL URL ÁTALAKÍTÁSA (DigitalOcean miatt)
# ============================================================
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# ============================================================
# HIBANAplóZÁS
# ============================================================
ERROR_LOG_FILE = 'error_log.txt'

def log_error(error_msg):
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{timestamp}] {error_msg}\n")
            f.write(traceback.format_exc())
            f.write("\n" + "-"*50 + "\n")
    except:
        pass

# ============================================================
# EMAIL KÜLDÉS ADMINNAK (podanyarpi@gmail.com)
# ============================================================
def send_admin_alert(subject, message):
    try:
        ADMIN_EMAIL = 'podanyarpi@gmail.com'
        GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
        GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
        
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[GlobalStore ALERT] {subject}"
        msg['From'] = GMAIL_EMAIL
        msg['To'] = ADMIN_EMAIL
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="background-color:#0f172a; padding:20px;">
            <div style="background:#1e293b; border-radius:16px; padding:24px;">
                <h1 style="color:#f59e0b;">⚠️ GlobalStore Alert!</h1>
                <p><strong>Time:</strong> {current_time}</p>
                <p><strong>Message:</strong> {message}</p>
                <p style="color:#94a3b8;">🔴 Action required!</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, ADMIN_EMAIL, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email hiba: {e}")
        return False

# ============================================================
# DAILYSTORE API FUNKCIÓK (ASZINKRON ELLENŐRZÉSHEZ)
# ============================================================
def check_dailystore_stock_async(sku, callback):
    """Aszinkron stock ellenőrzés (nem blokkolja a főszálat)"""
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/stock/{sku}', headers=headers, timeout=5)
        if response.status_code == 200:
            callback(response.json().get('stock', 0))
        else:
            callback(999)
    except:
        callback(999)

def check_dailystore_balance_async(callback):
    """Aszinkron balance ellenőrzés (nem blokkolja a főszálat)"""
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/balance', headers=headers, timeout=5)
        if response.status_code == 200:
            callback(response.json().get('balance', 0))
        else:
            callback(999)
    except:
        callback(999)

def check_dailystore_stock(sku):
    """Szinkron stock ellenőrzés (balance vásárláshoz)"""
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/stock/{sku}', headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('stock', 0)
        return 999
    except:
        return 999

def check_dailystore_balance():
    """Szinkron balance ellenőrzés (balance vásárláshoz)"""
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/balance', headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('balance', 0)
        return 999
    except:
        return 999

# ============================================================
# FLASK ALKALMAZÁS
# ============================================================
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kulcs123')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///globalstore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = os.getenv('STRIPE_API_KEY')
DAILYSTORE_API_KEY = os.getenv('DAILYSTORE_API_KEY')
DAILYSTORE_API_URL = os.getenv('DAILYSTORE_API_URL')

app.register_blueprint(admin_bp)
app.register_blueprint(app_bp)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================
# ADATBÁZIS LÉTREHOZÁSA
# ============================================================
with app.app_context():
    try:
        db.create_all()
        print("✅ Adatbázis kész!")
        
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('GlobalStore2024AdminSecure'),
                is_admin=True,
                balance=1000.0
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin létrehozva: admin / GlobalStore2024AdminSecure")
        
        if Product.query.count() == 0:
            print("⚠️ Nincsenek termékek! Használd az admin felületet.")
        
    except Exception as e:
        log_error(f"Indítási hiba: {str(e)}")

# ============================================================
# PUBLIKUS VÉGPONTOK
# ============================================================
@app.route('/')
def index():
    try:
        products = Product.query.filter_by(is_active=True).all()
        stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        return render_template('index.html', 
                             user=current_user, 
                             products=products, 
                             stripe_publishable_key=stripe_publishable_key)
    except Exception as e:
        log_error(f"Index hiba: {str(e)}")
        return "Hiba történt", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password, password):
                login_user(user)
                if user.is_admin:
                    return redirect(url_for('admin_bp.admin_dashboard'))
                return redirect(url_for('index'))
            flash('Hibás adatok', 'error')
        return render_template('login.html')
    except Exception as e:
        log_error(f"Login hiba: {str(e)}")
        return "Hiba történt", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            discord_id = request.form.get('discord_id')
            
            if User.query.filter_by(username=username).first():
                flash('Foglalt név', 'error')
                return redirect(url_for('register'))
            
            new_user = User(
                username=username,
                password=generate_password_hash(password),
                discord_id=discord_id
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))
        return render_template('register.html')
    except Exception as e:
        log_error(f"Register hiba: {str(e)}")
        return "Hiba történt", 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.purchased_at.desc()).all()
        stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        return render_template('user_dashboard.html', 
                             user=current_user, 
                             purchases=purchases,
                             stripe_publishable_key=stripe_publishable_key)
    except Exception as e:
        log_error(f"Dashboard hiba: {str(e)}")
        return "Hiba történt", 500

# ============================================================
# API VÉGPONTOK
# ============================================================
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'status': 'ok', 'message': 'API is working'})

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product_by_id(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify({
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'price': product.price,
            'daily_store_price': product.daily_store_price,
            'description': product.description,
            'category': product.category,
            'is_active': product.is_active
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Stripe PaymentIntent létrehozása - ASZINKRON DailyStore ellenőrzéssel"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        product_id = data.get('product_id')
        
        if amount:
            if not current_user.is_authenticated:
                return jsonify({'error': 'Login required'}), 401
            intent = stripe.PaymentIntent.create(
                amount=int(amount) * 100,
                currency='usd',
                metadata={'user_id': str(current_user.id), 'type': 'topup'},
                automatic_payment_methods={'enabled': True}
            )
            return jsonify({'clientSecret': intent.client_secret})
        
        elif product_id:
            product = Product.query.get(int(product_id))
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            # ASZINKRON ellenőrzések (nem blokkolják a Stripe hívást)
            stock_ok = [True]
            balance_ok = [True]
            stock_value = [0]
            balance_value = [0]
            
            def stock_callback(stock):
                stock_value[0] = stock
                stock_ok[0] = stock > 0
            
            def balance_callback(balance):
                balance_value[0] = balance
                balance_ok[0] = balance >= product.daily_store_price
            
            # Indítjuk az aszinkron ellenőrzéseket
            threading.Thread(target=check_dailystore_stock_async, args=(product.sku, stock_callback)).start()
            threading.Thread(target=check_dailystore_balance_async, args=(balance_callback,)).start()
            
            # Stripe PaymentIntent létrehozása (nem várjuk meg az ellenőrzéseket)
            intent = stripe.PaymentIntent.create(
                amount=int(product.price * 100),
                currency='usd',
                metadata={
                    'user_id': str(current_user.id),
                    'product_id': product_id, 
                    'type': 'purchase',
                    'product_sku': product.sku
                },
                automatic_payment_methods={'enabled': True}
            )
            
            # Ha az ellenőrzések gyorsak, naplózzuk az eredményt (nem blokkol)
            def log_check_results():
                import time
                time.sleep(2)  # Várunk 2 másodpercet az ellenőrzésekre
                if not stock_ok[0]:
                    send_admin_alert("⚠️ Out of Stock Alert!", f"Product {product.name} (SKU: {product.sku}) is out of stock! Stock: {stock_value[0]}")
                if not balance_ok[0]:
                    send_admin_alert("⚠️ Low DailyStore Balance!", f"Balance: ${balance_value[0]:.2f}, Need: ${product.daily_store_price:.2f}")
            
            threading.Thread(target=log_check_results).start()
            
            return jsonify({'clientSecret': intent.client_secret})
        
        return jsonify({'error': 'Invalid request'}), 400
    except Exception as e:
        log_error(f"PaymentIntent hiba: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/purchase/with-balance', methods=['POST'])
@login_required
def purchase_with_balance():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        
        product = Product.query.get(int(product_id))
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if current_user.balance < product.price:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Stock ellenőrzés (szinkron, mert itt kell a válasz)
        stock = check_dailystore_stock(product.sku)
        if stock <= 0:
            return jsonify({
                'error': f'Sorry, {product.name} is currently out of stock.',
                'error_type': 'out_of_stock'
            }), 404
        
        # Balance ellenőrzés (szinkron, mert itt kell a válasz)
        ds_balance = check_dailystore_balance()
        if ds_balance < product.daily_store_price:
            send_admin_alert("Low DailyStore Balance!", f"Need ${product.daily_store_price}, have ${ds_balance}")
            return jsonify({
                'error': 'Our store is currently restocking. Please try again later.',
                'error_type': 'dailystore_balance'
            }), 503
        
        # Vásárlás a DailyStore-ból
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}', 'Content-Type': 'application/json'}
        purchase_data = {'items': [{'sku': product.sku, 'quantity': 1}]}
        
        ds_response = requests.post(
            f'{DAILYSTORE_API_URL}/purchase',
            headers=headers,
            json=purchase_data
        )
        
        if ds_response.status_code != 201:
            error_data = ds_response.json()
            error_msg = error_data.get('message', 'Unknown error')
            return jsonify({'error': f'API error: {error_msg}'}), 500
        
        ds_result = ds_response.json()
        credentials = []
        for item in ds_result.get('items', []):
            if item.get('credentials'):
                credentials.extend(item['credentials'])
        
        # Levonás a felhasználótól
        current_user.balance -= product.price
        
        purchase = Purchase(
            user_id=current_user.id,
            product_id=product.id,
            price_paid=product.price,
            daily_store_order_id=ds_result.get('orderId'),
            credentials=json.dumps(credentials)
        )
        db.session.add(purchase)
        
        transaction = Transaction(
            user_id=current_user.id,
            amount=-product.price,
            type='purchase',
            description=f'Vásárlás: {product.name}'
        )
        db.session.add(transaction)
        db.session.commit()
        
        if '@' in current_user.username:
            send_purchase_email(current_user.username, product.name, credentials)
        
        return jsonify({
            'success': True, 
            'new_balance': current_user.balance, 
            'credentials': credentials
        })
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Purchase hiba: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if not endpoint_secret:
            return 'Webhook secret not configured', 500
            
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        
        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            metadata = intent.get('metadata', {})
            
            if metadata.get('type') == 'topup':
                user = User.query.get(int(metadata['user_id']))
                if user:
                    amount = intent['amount'] / 100
                    user.balance += amount
                    db.session.commit()
                    print(f"✅ {user.username} +${amount}")
            
            elif metadata.get('type') == 'purchase':
                product_id = metadata.get('product_id')
                user_id = metadata.get('user_id')
                
                if product_id and user_id:
                    product = Product.query.get(int(product_id))
                    user = User.query.get(int(user_id))
                    
                    if product and user:
                        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}', 'Content-Type': 'application/json'}
                        purchase_data = {'items': [{'sku': product.sku, 'quantity': 1}]}
                        
                        ds_response = requests.post(
                            f'{DAILYSTORE_API_URL}/purchase',
                            headers=headers,
                            json=purchase_data
                        )
                        
                        if ds_response.status_code == 201:
                            ds_result = ds_response.json()
                            credentials = []
                            for item in ds_result.get('items', []):
                                if item.get('credentials'):
                                    credentials.extend(item['credentials'])
                            
                            purchase = Purchase(
                                user_id=user.id,
                                product_id=product.id,
                                price_paid=intent['amount'] / 100,
                                daily_store_order_id=ds_result.get('orderId'),
                                credentials=json.dumps(credentials),
                                payment_method='stripe'
                            )
                            db.session.add(purchase)
                            db.session.commit()
                            
                            if '@' in user.username:
                                send_purchase_email(user.username, product.name, credentials)
        
        return 'Success', 200
    except Exception as e:
        log_error(f"Webhook hiba: {str(e)}")
        return 'Error', 400

# ============================================================
# ADMIN API
# ============================================================
@app.route('/api/admin/send-balance', methods=['POST'])
@login_required
def admin_send_balance():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        username = data.get('username')
        amount = float(data.get('amount', 0))
        action = data.get('action')
        
        target_user = User.query.filter_by(username=username).first()
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        if action == 'add':
            target_user.balance += amount
        elif action == 'remove':
            if target_user.balance < amount:
                return jsonify({'error': 'Insufficient balance'}), 400
            target_user.balance -= amount
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        return jsonify({'success': True, 'new_balance': target_user.balance})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)