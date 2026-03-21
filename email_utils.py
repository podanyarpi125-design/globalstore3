# email_utils.py
import os
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_purchase_email(user_email, product_name, credentials):
    """Email küldés a vásárlásról Gmailen keresztül - PROFESSIONAL verzió"""
    
    # Gmail beállítások a .env-ből
    GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
    GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
    
    # Ellenőrizzük, hogy van-e email cím
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        print("❌ Gmail beállítások hiányoznak a .env fájlból!")
        return False
    
    # Ha nincs email cím (pl. username @ nélkül), akkor nem küldünk
    if '@' not in user_email:
        print(f"❌ Nem email cím: {user_email}")
        return False
    
    try:
        # Email összeállítása
        message = MIMEMultipart("alternative")
        message["Subject"] = f"✅ Köszönjük a vásárlást: {product_name}"
        message["From"] = GMAIL_EMAIL
        message["To"] = user_email
        
        # Credential-ök formázása
        if isinstance(credentials, list):
            creds_text = "\n".join(credentials)
        elif isinstance(credentials, str):
            try:
                # Ha JSON string, akkor szépen formázzuk
                creds_json = json.loads(credentials)
                if isinstance(creds_json, list):
                    creds_text = "\n".join(creds_json)
                else:
                    creds_text = json.dumps(creds_json, indent=2)
            except:
                creds_text = credentials
        else:
            creds_text = str(credentials)
        
        # Aktuális dátum
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # HTML verzió (SZÉP DESIGN - a régiből)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            </style>
        </head>
        <body style="margin:0; padding:0; background-color:#0f172a; font-family: 'Inter', Arial, sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a; padding:20px;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#1e293b; border-radius:16px; border:1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
                            <!-- Header with Logo -->
                            <tr>
                                <td style="padding:40px 30px 20px 30px; text-align:center;">
                                    <div style="font-size:64px; color:#3b82f6; margin-bottom:20px; background: rgba(59,130,246,0.1); width:100px; height:100px; line-height:100px; border-radius:50%; margin-left:auto; margin-right:auto;">✅</div>
                                    <h1 style="color:#ffffff; margin:0; font-size:32px; font-weight:700;">Sikeres vásárlás!</h1>
                                    <p style="color:#94a3b8; margin-top:10px; font-size:16px;">Köszönjük, hogy a GlobalStore-t választottad!</p>
                                </td>
                            </tr>
                            
                            <!-- Termék adatok -->
                            <tr>
                                <td style="padding:0 30px 20px 30px;">
                                    <div style="background-color:#0f172a; border-radius:12px; padding:25px; border:1px solid #334155;">
                                        <h2 style="color:#3b82f6; font-size:20px; margin-top:0; margin-bottom:20px; display:flex; align-items:center; gap:10px;">
                                            <span style="font-size:24px;">📦</span> Termék részletek
                                        </h2>
                                        <table width="100%" style="color:#ffffff;">
                                            <tr>
                                                <td style="padding:8px 0; color:#94a3b8; width:100px;">Termék:</td>
                                                <td style="padding:8px 0; font-weight:600;">{product_name}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding:8px 0; color:#94a3b8;">Dátum:</td>
                                                <td style="padding:8px 0;">{current_date}</td>
                                            </tr>
                                        </table>
                                    </div>
                                </td>
                            </tr>
                            
                            <!-- Belépési adatok -->
                            <tr>
                                <td style="padding:0 30px 20px 30px;">
                                    <div style="background-color:#0f172a; border-radius:12px; padding:25px; border:1px solid #334155;">
                                        <h2 style="color:#3b82f6; font-size:20px; margin-top:0; margin-bottom:20px; display:flex; align-items:center; gap:10px;">
                                            <span style="font-size:24px;">🔐</span> Belépési adatok
                                        </h2>
                                        <div style="background-color:#1e293b; border-radius:8px; padding:20px; border:1px solid #334155;">
                                            <pre style="color:#4ade80; margin:0; font-family: 'Courier New', monospace; font-size:14px; white-space: pre-wrap; word-break: break-all;">{creds_text}</pre>
                                        </div>
                                        <p style="color:#f59e0b; font-size:13px; margin-top:15px; display:flex; align-items:center; gap:5px;">
                                            ⚠️ <strong>Fontos:</strong> Ezeket az adatokat tartsd biztonságos helyen! Ne oszd meg másokkal!
                                        </p>
                                    </div>
                                </td>
                            </tr>
                            
                            <!-- Támogatás -->
                            <tr>
                                <td style="padding:0 30px 30px 30px;">
                                    <div style="background-color:#2d3748; border-radius:12px; padding:20px; text-align:center;">
                                        <p style="color:#94a3b8; margin:0 0 10px 0;">📞 Segítségre van szükséged?</p>
                                        <p style="color:#ffffff; margin:0;">
                                            Vedd fel velünk a kapcsolatot a <a href="mailto:{GMAIL_EMAIL}" style="color:#3b82f6; text-decoration:none;">{GMAIL_EMAIL}</a> címen
                                        </p>
                                    </div>
                                </td>
                            </tr>
                            
                            <!-- Footer -->
                            <tr>
                                <td style="padding:20px 30px 30px 30px; text-align:center; border-top:1px solid #334155;">
                                    <p style="color:#64748b; font-size:12px; margin:5px 0;">
                                        © 2026 GlobalStore. Minden jog fenntartva.
                                    </p>
                                    <p style="color:#64748b; font-size:11px; margin:5px 0;">
                                        Ez egy automatikus email, kérjük ne válaszolj rá.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        # Text verzió (ha nem támogatja a HTML-t)
        text = f"""
✅ Sikeres vásárlás - GlobalStore

--------------------------------
TERMÉK RÉSZLETEK
--------------------------------
Termék: {product_name}
Dátum: {current_date}

--------------------------------
BELÉPÉSI ADATOK
--------------------------------
{creds_text}

--------------------------------
⚠️ Fontos: Ezeket az adatokat tartsd biztonságos helyen!

--------------------------------
GlobalStore - Premium Digital Goods
Email: {GMAIL_EMAIL}

© 2026 GlobalStore
        """
        
        # Csatoljuk mindkét verziót
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        
        # SMTP kapcsolat Gmailhez
        print(f"📧 Email küldése {user_email} címre...")
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, user_email, message.as_string())
        server.quit()
        
        print(f"✅ Email sikeresen elküldve: {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Email hiba: {str(e)}")
        return False