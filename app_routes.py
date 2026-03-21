# app_routes.py
from flask import Blueprint, jsonify, request
from models import db, User, Product, Purchase, Transaction
import json
import requests
import os
from email_utils import send_purchase_email

app_bp = Blueprint('app_bp', __name__, url_prefix='/api')

DAILYSTORE_API_KEY = os.getenv('DAILYSTORE_API_KEY')
DAILYSTORE_API_URL = os.getenv('DAILYSTORE_API_URL')

@app_bp.route('/products', methods=['GET'])
def get_products():
    try:
        products = Product.query.filter_by(is_active=True).all()
        return jsonify([{
            'id': p.id, 'sku': p.sku, 'name': p.name,
            'price': p.price, 'description': p.description
        } for p in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app_bp.route('/bot/check_balance/<discord_id>', methods=['GET'])
def bot_check_balance(discord_id):
    try:
        user = User.query.filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'username': user.username, 'balance': user.balance})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app_bp.route('/bot/purchase', methods=['POST'])
def bot_purchase():
    try:
        data = request.get_json()
        discord_id = data.get('discord_id')
        product_id = data.get('product_id')
        
        user = User.query.filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        product = Product.query.get(int(product_id))
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if user.balance < product.price:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}', 'Content-Type': 'application/json'}
        purchase_data = {'items': [{'sku': product.sku, 'quantity': 1}]}
        
        ds_response = requests.post(f'{DAILYSTORE_API_URL}/purchase', headers=headers, json=purchase_data)
        
        if ds_response.status_code != 201:
            return jsonify({'error': 'API error'}), 500
        
        ds_result = ds_response.json()
        credentials = []
        for item in ds_result.get('items', []):
            if item.get('credentials'):
                credentials.extend(item['credentials'])
        
        user.balance -= product.price
        
        purchase = Purchase(
            user_id=user.id,
            product_id=product.id,
            price_paid=product.price,
            daily_store_order_id=ds_result.get('orderId'),
            credentials=json.dumps(credentials)
        )
        db.session.add(purchase)
        db.session.commit()
        
        if '@' in user.username:
            send_purchase_email(user.username, product.name, credentials)
        
        return jsonify({'success': True, 'new_balance': user.balance, 'credentials': credentials})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500