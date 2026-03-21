# app.py - CSAK A BALANCE ELLENŐRZÉS RÉSZ (a teljes fájlban ezek a részek változnak)

# ============================================================
# DAILYSTORE API FUNKCIÓK - JAVÍTOTT
# ============================================================
def check_dailystore_stock(sku):
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/stock/{sku}', headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            stock = data.get('stock', 0)
            print(f"📦 Stock for {sku}: {stock}")
            return stock
        elif response.status_code == 404:
            print(f"⚠️ Product not found: {sku}")
            return 0
        else:
            print(f"⚠️ Stock API error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"⚠️ Stock timeout for {sku}")
        return None
    except Exception as e:
        print(f"⚠️ Stock error: {e}")
        return None

def check_dailystore_balance():
    try:
        headers = {'Authorization': f'Bearer {DAILYSTORE_API_KEY}'}
        response = requests.get(f'{DAILYSTORE_API_URL}/balance', headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            balance = data.get('balance', 0)
            print(f"💰 DailyStore balance: ${balance}")
            return balance
        else:
            print(f"⚠️ Balance API error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("⚠️ Balance timeout")
        return None
    except Exception as e:
        print(f"⚠️ Balance error: {e}")
        return None

# ============================================================
# A create_payment_intent végpontban a balance ellenőrzés:
# ============================================================
# 2. DAILYSTORE BALANCE ELLENŐRZÉS
ds_balance = check_dailystore_balance()

# Ha nem tudtuk lekérni a balance-t (timeout vagy hiba)
if ds_balance is None:
    print("⚠️ Balance check failed - allowing purchase (will check later)")
    # Nem blokkoljuk a fizetést, csak naplózunk
    # Később a webhook-ban majd ellenőrizzük
elif ds_balance < product.daily_store_price:
    send_admin_alert("⚠️ LOW DAILYSTORE BALANCE!", 
        f"Balance: ${ds_balance:.2f}, Need: ${product.daily_store_price:.2f} for {product.name}")
    return jsonify({
        'error': f'Insufficient store balance to complete your purchase. Required: ${product.daily_store_price:.2f}, Available: ${ds_balance:.2f}. Please contact support.',
        'error_type': 'insufficient_dailystore_balance',
        'required': product.daily_store_price,
        'available': ds_balance
    }), 503