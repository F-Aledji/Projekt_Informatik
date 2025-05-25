from datetime import datetime
from flask import Flask, session, redirect, url_for, request, jsonify, flash, render_template
from flask_sqlalchemy import SQLAlchemy
import requests

# Flask-Anwendung initialisieren, die Grundlage für Webserver und Routing ist
app = Flask(__name__)
app.secret_key = 'secret_key_project'  # Wichtig für sichere Sessions (Cookies)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  # DB-Verbindung zu SQLite-Datei
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Verhindert unnötiges Tracking (Performance)

# SQLAlchemy bindet die Datenbank an die App, ermöglicht ORM-Zugriff (Objekte statt SQL)
db = SQLAlchemy(app)


# Datenbankmodell für Nutzerkonten
# Spalten: ID (Primärschlüssel), Benutzername, Passwort, E-Mail, Registrierungszeit, Land
# Benutzername und E-Mail sind eindeutig (unique)
class db_user(db.Model):
    _id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)  # Hinweis: Passwort hier unverschlüsselt (kein Hash!)
    email = db.Column(db.String(150), unique=True, nullable=False)
    creation = db.Column(db.DateTime, default=datetime.now)  # Zeitstempel der Erstellung
    country = db.Column(db.String(150), nullable=True)

    def __init__(self, username, password, email, country):
        self.username = username
        self.password = password
        self.email = email
        self.country = country


# Datenbankmodell für "gelikte" Produkte
# Verknüpft Nutzername mit Produktnamen, damit man Favoriten speichert
class db_liked_product(db.Model):
    _id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)  # Fremdschlüssel zu Nutzername (logisch)
    product = db.Column(db.String(150), nullable=False)   # Produktname


# Context-Processor: Fügt allen Templates die Anzahl der registrierten Nutzer hinzu
# Wird automatisch in jedem Template als Variable "user_count" verfügbar sein
@app.context_processor
def inject_user_count():
    return {"user_count": db_user.query.count()}  # Anzahl aller Nutzer aus DB


# Route zum Registrieren neuer Nutzer (URL: /register)
# GET-Anfrage zeigt das Registrierungsformular an
# POST-Anfrage verarbeitet Formulardaten, prüft auf Duplikate und speichert neuen Nutzer
# Datenherkunft: Formularfelder username, email, password, country (aus HTTP POST)
# Bei Fehlern wird mit Flash-Meldung zurück zum Formular geleitet
# Bei Erfolg weiter zur Login-Seite
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        email = request.form['email']
        password = request.form['password']
        country = request.form['country']

        # Prüfen, ob Email oder Username bereits vergeben sind (Daten aus DB-Abfragen)
        if db_user.query.filter_by(email=email).first():
            flash("Diese Email wird schon verwendet ! :(", "warning")
            return redirect(url_for('register'))

        if db_user.query.filter_by(username=user).first():
            flash("Dieser Benutzername wird schon verwendet ! :( ", "warning")
            return redirect(url_for('register'))

        # Wenn Daten ok, neuen Benutzer anlegen und speichern
        new_user = db_user(user, password, email, country)
        db.session.add(new_user)
        db.session.commit()

        flash("Benutzer erfolgreich registriert ! :)", "success")
        return redirect(url_for('login'))

    # GET: Registrierungsformular anzeigen (HTML Template)
    return render_template('register.html')


# Login-Route (URL: /login)
# GET zeigt Login-Formular an
# POST prüft eingegebene Daten mit DB-Einträgen ab
# Session wird bei Erfolg mit Username und gelikten Produkten gefüllt
# Flash-Meldungen informieren über Fehler (Benutzer nicht gefunden, falsches Passwort)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_data' in session:
        flash("Du bist bereits eingeloggt", "warning")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        # Nutzer aus DB suchen, Passwort prüfen
        user_data = db_user.query.filter_by(username=user).first()

        if user_data and user_data.password == password:
            # Session speichern: Username + Liste gelikter Produkte (aus DB geladen)
            session['user_data'] = user_data.username
            likes = db_liked_product.query.filter_by(username=user_data.username).all()
            session['liked_products'] = [like.product for like in likes]

            flash("Erfolgreich eingeloggt", "success")
            return redirect(url_for('home'))
        
        elif not user_data:
            flash("Benutzername nicht gefunden. Bitte zu erst registrieren", "warning")
            return redirect(url_for('register'))
        else:
            flash("Benutzername oder Passwort falsch", "warning")
            return redirect(url_for('login'))

    # GET: Login-Formular anzeigen
    return render_template('login.html')


# Logout-Route (URL: /logout)
# Sichert gelikte Produkte aus Session in DB (falls noch nicht gespeichert)
# Löscht Session-Daten (Logout)
# Redirect zur Startseite
@app.route('/logout')
def logout():
    if 'user_data' in session:
        liked_products = session.get('liked_products', [])
        # Für alle Produkte in Session prüfen, ob schon in DB; falls nicht, hinzufügen
        for product in liked_products:
            if not db_liked_product.query.filter_by(username=session['user_data'], product=product).first():
                db.session.add(db_liked_product(username=session['user_data'], product=product))
        db.session.commit()
    
    # Session leeren (Logout)
    session.pop('user_data', None)
    session.pop('liked_products', None)
    flash("Erfolgreich ausgeloggt", "success")
    return redirect(url_for('index'))


# Route zum "Liken" eines Produkts (AJAX POST mit JSON)
# Erwartet JSON mit Feld "title" = Produktname
# Prüft, ob Produkt schon gelikt (in DB)
# Fügt neuen Like hinzu oder aktualisiert Session
# Gibt JSON-Response zurück für Frontend (AJAX)
@app.route('/like', methods=['POST'])
def like():
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data provided"), 400
    product_title = data.get('title')

    if not product_title:
        return jsonify(success=False, message="No product title provided"), 400

    current_username = session['user_data']
    liked_in_session = session.get('liked_products', [])

    existing_db_like = db_liked_product.query.filter_by(username=current_username, product=product_title).first()
    if existing_db_like:
        # Produkt bereits gelikt, nur Session ggf. ergänzen
        flash(f'"{product_title}" ist bereits in deinen Favoriten.', 'warning')
        if product_title not in liked_in_session:
            liked_in_session.append(product_title)
            session['liked_products'] = liked_in_session
    else:
        # Neues Like speichern (DB + Session)
        new_db_like = db_liked_product(username=current_username, product=product_title)
        db.session.add(new_db_like)
        db.session.commit()
        if product_title not in liked_in_session:
            liked_in_session.append(product_title)
            session['liked_products'] = liked_in_session
        flash(f'"{product_title}" wurde zu deinen Favoriten hinzugefügt!', 'success')
    
    # JSON-Response an Client
    return jsonify(success=True, message=f"Like status for {product_title} updated."), 200


# Route zum Entfernen eines gelikten Produkts (POST)
# Erwartet Formulardaten mit Feld "title"
# Löscht Eintrag aus DB und aktualisiert Session
# Redirect zurück auf Favoriten-Seite
@app.route('/unlike', methods=['POST'])
def unlike():
    current_username = session.get('user_data')
    if not current_username:
        flash("Sitzungsfehler oder nicht eingeloggt.", "danger")
        return redirect(url_for('login'))

    product_to_unlike = request.form.get('title')
    liked = session.get('liked_products', [])

    if not product_to_unlike:
        flash("Kein Produkt angegeben", "warning")
        return redirect(url_for('favorites'))
    
    # DB-Eintrag löschen, wenn vorhanden
    db_product_entry = db_liked_product.query.filter_by(username=current_username, product=product_to_unlike).first()
    if db_product_entry:
        db.session.delete(db_product_entry)
        db.session.commit()
        flash(f'Das Produkt "{product_to_unlike}" gefällt dir nicht mehr', 'success')

        # Auch aus Session entfernen
        if product_to_unlike in liked:
            liked.remove(product_to_unlike)
            session['liked_products'] = liked
            session.modified = True
    else:
        flash(f'Das Produkt "{product_to_unlike}" ist nicht in deinen Favoriten', 'warning')

    return redirect(url_for('favorites'))


# Index-Route (Startseite)
# Einfaches Template ohne Login-Abfrage
@app.route('/')
def index():
    return render_template('index.html')


# Home-Route (eingeloggte Nutzer)
# Prüft, ob Nutzer eingeloggt (Session)
# Zeigt personalisierte Seite mit Usernamen
@app.route('/home')
def home():
    if 'user_data' in session:
        user_data = session['user_data']
        return render_template('home.html', user_data=user_data)
    else:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))


# Profilseite
# Zeigt User-Daten und Liste der gelikten Produkte (nur Produktnamen)
# Daten aus DB, nur für eingeloggte Nutzer zugänglich
@app.route('/profile')
def profile():
    if 'user_data' not in session:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))
    
    user = db_user.query.filter_by(username=session['user_data']).first()
    liked_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]

    return render_template('profile.html', user=user, liked_products=liked_products)


# Favoriten-Seite
# Zeigt alle gelikten Produkte mit Detailinfos von externer API
# Holt Produktliste (limit 20) per HTTP GET von DummyJSON API
# Filtert nur Produkte heraus, die Nutzer gelikt hat (Daten aus DB)
# Bei Fehlern (API down) wird zur Home-Seite weitergeleitet mit Fehlermeldung
@app.route('/favorites')
def favorites():
    if 'user_data' not in session:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))
    
    user = db_user.query.filter_by(username=session['user_data']).first()
    liked_db_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]

    try:
        response = requests.get("https://dummyjson.com/products?limit=20")
        response.raise_for_status()
        api_get_all_products = response.json().get("products", [])
    except requests.exceptions.RequestException as e:
        flash(f"Fehler beim Abrufen der Produktdaten {e}", "warning")
        return redirect(url_for('home'))
    
    liked_products = []
    for product in api_get_all_products:
        if product["title"] in liked_db_products:
            liked_products.append(product)

    return render_template('favorites.html', user=user, liked_products=liked_products)


# Debug-Route zum Anzeigen der Session-Daten als JSON (für Entwickler)
# Kann genutzt werden, um Session-Inhalte im Browser zu prüfen
@app.route('/debug-session')
def debug_session_view():
    session_as_dict = dict(session)
    return jsonify(session_as_dict)


# Startet die App mit Debug-Modus, erstellt DB-Tabellen falls nötig
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)