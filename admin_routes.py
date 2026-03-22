# admin_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Product, Purchase, Transaction
import json

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    products = Product.query.all()
    purchases = Purchase.query.order_by(Purchase.purchased_at.desc()).limit(20).all()
    return render_template('admin_dashboard.html', users=users, products=products, purchases=purchases)

# ============================================================
# TERMÉK KEZELÉS
# ============================================================
@admin_bp.route('/products/manage')
@login_required
def manage_products():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    products = Product.query.all()
    return render_template('admin_products.html', products=products)

@admin_bp.route('/products/add', methods=['POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        
        sku = data.get('sku', '').strip()
        name = data.get('name', '').strip()
        price = float(data.get('price', 0))
        daily_store_price = float(data.get('daily_store_price', price))
        description = data.get('description', '')
        category = data.get('category', '')
        
        if not sku or not name or price <= 0:
            return jsonify({'error': 'SKU, name and price are required'}), 400
        
        existing = Product.query.filter_by(sku=sku).first()
        if existing:
            return jsonify({'error': f'Product with SKU "{sku}" already exists'}), 400
        
        new_product = Product(
            sku=sku,
            name=name,
            description=description,
            price=price,
            daily_store_price=daily_store_price,
            category=category,
            is_active=True
        )
        db.session.add(new_product)
        db.session.commit()
        
        return jsonify({'success': True, 'product': {'id': new_product.id, 'sku': new_product.sku, 'name': new_product.name}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/products/update/<int:product_id>', methods=['PUT'])
@login_required
def update_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            product.name = data['name']
        if 'price' in data:
            product.price = float(data['price'])
        if 'daily_store_price' in data:
            product.daily_store_price = float(data['daily_store_price'])
        if 'description' in data:
            product.description = data['description']
        if 'category' in data:
            product.category = data['category']
        if 'is_active' in data:
            product.is_active = data['is_active']
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/products/delete/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================
# BULK ADD PRODUCTS (ÚJ VÉGPONT!)
# ============================================================
@admin_bp.route('/products/bulk-add', methods=['POST'])
@login_required
def bulk_add_products():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        products = data.get('products', [])
        
        added = 0
        skipped = 0
        errors = []
        
        for p in products:
            sku = p.get('sku', '').strip()
            name = p.get('name', '').strip()
            price = float(p.get('price', 0))
            daily_store_price = float(p.get('daily_store_price', price))
            description = p.get('description', '')
            category = p.get('category', '')
            
            if not sku or not name or price <= 0:
                errors.append(f"Hiányzó adatok: {sku or 'ismeretlen'}")
                continue
            
            existing = Product.query.filter_by(sku=sku).first()
            if existing:
                skipped += 1
                continue
            
            new_product = Product(
                sku=sku,
                name=name,
                description=description,
                price=price,
                daily_store_price=daily_store_price,
                category=category,
                is_active=True
            )
            db.session.add(new_product)
            added += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'added': added, 
            'skipped': skipped,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================
# EGYÉB ADMIN VÉGPONTOK
# ============================================================
@admin_bp.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify([{
        'id': u.id, 'username': u.username, 'balance': u.balance, 
        'discord_id': u.discord_id, 'is_admin': u.is_admin
    } for u in User.query.all()])

@admin_bp.route('/purchases')
@login_required
def get_purchases():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    purchases = Purchase.query.order_by(Purchase.purchased_at.desc()).all()
    return jsonify([{
        'id': p.id, 'user': p.user.username, 'product': p.product.name if p.product else 'Unknown',
        'price_paid': p.price_paid, 'payment_method': p.payment_method,
        'credentials': json.loads(p.credentials) if p.credentials else [],
        'purchased_at': p.purchased_at.strftime('%Y-%m-%d %H:%M')
    } for p in purchases])

@admin_bp.route('/send-balance', methods=['POST'])
@login_required
def send_balance():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        user = User.query.filter_by(username=data['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        amount = float(data['amount'])
        if data['action'] == 'add':
            user.balance += amount
        elif data['action'] == 'remove':
            if user.balance < amount:
                return jsonify({'error': 'Insufficient balance'}), 400
            user.balance -= amount
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        return jsonify({'success': True, 'new_balance': user.balance})
    except Exception as e:
        return jsonify({'error': str(e)}), 500