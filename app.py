# - Flask: Hauptobjekt für die Web-App.
# - session: Zum Speichern von User-Daten über mehrere Anfragen hinweg (z.B. ob jemand eingeloggt ist).
# - redirect: Leitet den Browser auf eine andere Seite um.
# - url_for: Erzeugt URLs für Funktionen, super praktisch, wenn sich Routen ändern.
# - request: Zugriff auf alle Daten der aktuellen Anfrage (Formularfelder, JSON etc.).
# - jsonify: Python-Daten in JSON umwandeln, gut für API-Antworten.
# - flash: Kurzlebige Nachrichten (z.B. "Erfolgreich eingeloggt!") anzeigen.
# - render_template: Lädt HTML-Dateien (Templates) und schickt sie an den Browser.

from datetime import datetime                                                                 # Importiert 'datetime' für Zeitstempel, z.B. wann ein User registriert wurde.
from flask import Flask, session, redirect, url_for, request, jsonify, flash, render_template # Wichtige Flask-Module:

from flask_sqlalchemy import SQLAlchemy                                                       # Das ist das ORM-Tool, um einfach mit der Datenbank zu sprechen, ohne viel SQL schreiben zu müssen.
import requests                                                                               # Importiert 'requests', um HTTP-Anfragen an externe APIs zu senden (hier für die Produktdaten).

# Flask App initialisieren. Das ist quasi der Startpunkt der Anwendung.
app = Flask(__name__)
app.secret_key = 'secret_key_project'  # Ein geheimer Schlüssel, super wichtig für sichere Sessions (Cookies). Ohne den könnte jemand Sessions manipulieren.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  # Definiert, wo die Datenbank liegt. Hier wird eine einfache SQLite-Datei genutzt.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Eine SQLAlchemy-Einstellung. Deaktiviert das Tracking von Objektänderungen, was die Performance verbessert.

# Datenbank-Objekt erstellen und mit der Flask-App verbinden.
db = SQLAlchemy(app)


# Datenbankmodell für User-Accounts. Jede Zeile in der 'db_user'-Tabelle ist ein User.
class db_user(db.Model):
    _id = db.Column(db.Integer, primary_key=True) # Eindeutige ID für jeden User, wird automatisch vergeben.
    username = db.Column(db.String(150), unique=True, nullable=False) # Benutzername, muss einzigartig sein und darf nicht leer sein.
    password = db.Column(db.String(150), nullable=False)  # Passwort, darf nicht leer sein. WICHTIG: In echten Apps würde man Passwörter HASHEN!
    email = db.Column(db.String(150), unique=True, nullable=False) # E-Mail, muss auch einzigartig sein und darf nicht leer sein.
    creation = db.Column(db.DateTime, default=datetime.now)  # Zeitstempel, wann der User erstellt wurde. Standard ist die aktuelle Zeit.
    country = db.Column(db.String(150), nullable=True) # Land des Users, ist optional.

    # Konstruktor: Wird aufgerufen, wenn ein neuer User erstellt wird.
    def __init__(self, username, password, email, country):
        self.username = username
        self.password = password
        self.email = email
        self.country = country


# Datenbankmodell für gelikte Produkte. Speichert, welcher User welches Produkt mag.
class db_liked_product(db.Model):
    _id = db.Column(db.Integer, primary_key=True)                       # Eindeutige ID für jeden "Like"-Eintrag.
    username = db.Column(db.String(150), nullable=False)                # Der User, der das Produkt gelikt hat.
    product = db.Column(db.String(150), nullable=False)                 # Der Name des gelikten Produkts.


# Startseite der Anwendung. Erreichbar unter '/'.
@app.route('/')
def index():
    return render_template('index.html') # Zeigt die 'index.html' an.


# Route für die Registrierung neuer User. Erreichbar unter '/register'.
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Wenn das Formular abgeschickt wurde (POST-Anfrage):
    if request.method == 'POST':
        user = request.form['username']                                 # Holt den Usernamen aus dem Formular.
        email = request.form['email']                                   # Holt die E-Mail aus dem Formular.
        password = request.form['password']                             # Holt das Passwort aus dem Formular.
        country = request.form['country']                               # Holt das Land aus dem Formular.

        # Prüfen, ob E-Mail schon vergeben ist.
        if db_user.query.filter_by(email=email).first():
            flash("Email existiert schon!", "warning") # Nachricht an den User.
            return redirect(url_for('register')) # Zurück zum Registrierungsformular.

        # Prüfen, ob Username schon vergeben ist.
        if db_user.query.filter_by(username=user).first():
            flash("Username existiert schon!", "warning") # Nachricht an den User.
            return redirect(url_for('register')) # Zurück zum Registrierungsformular.

        # Neuen User in der Datenbank speichern.
        new_user = db_user(user, password, email, country)
        db.session.add(new_user) # User zur Session hinzufügen.
        db.session.commit() # Änderungen in der DB speichern.

        flash("Registrierung erfolgreich!", "success") # Erfolgsmeldung.
        return redirect(url_for('login')) # Weiter zur Login-Seite.

    # Wenn die Seite nur aufgerufen wird (GET-Anfrage):
    return render_template('register.html') # Registrierungsformular anzeigen.


# Route für den Login. Erreichbar unter '/login'.
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Wenn der User schon eingeloggt ist, direkt zur Home-Seite.
    if 'user_data' in session:
        flash("Bereits eingeloggt", "warning")
        return redirect(url_for('home'))
    
    # Wenn das Login-Formular abgeschickt wurde (POST-Anfrage):
    if request.method == 'POST':
        user = request.form['username'] # Holt den Usernamen.
        password = request.form['password'] # Holt das Passwort.

        user_data = db_user.query.filter_by(username=user).first() # User in DB suchen.

        # Wenn User gefunden und Passwort stimmt:
        if user_data and user_data.password == password:
            session['user_data'] = user_data.username # Usernamen in Session speichern.
            # Gelikte Produkte des Users aus DB holen und in Session speichern.
            likes = db_liked_product.query.filter_by(username=user_data.username).all()
            session['liked_products'] = [like.product for like in likes]

            flash("Login erfolgreich!", "success") # Erfolgsmeldung.
            return redirect(url_for('home')) # Weiter zur Home-Seite.
        
        # Wenn User nicht gefunden:
        elif not user_data:
            flash("Benutzer nicht gefunden!", "warning")
            return redirect(url_for('register')) # Zum Registrieren leiten.
        # Wenn Passwort falsch:
        else:
            flash("Falsches Passwort!", "warning")
            return redirect(url_for('login')) # Zurück zum Login.

    # Wenn die Seite nur aufgerufen wird (GET-Anfrage):
    return render_template('login.html') # Login-Formular anzeigen.


# Route für den Logout. Erreichbar unter '/logout'.
@app.route('/logout')
def logout():
    # Vor dem Logout: Aktuelle Likes aus der Session in die DB speichern, falls neue dazugekommen sind.
    if 'user_data' in session:
        liked_products = session.get('liked_products', [])
        for product in liked_products:
            # Nur speichern, wenn noch nicht in DB.
            if not db_liked_product.query.filter_by(username=session['user_data'], product=product).first():
                db.session.add(db_liked_product(username=session['user_data'], product=product))
        db.session.commit() # Änderungen speichern.
    
    # Session leeren, um den User auszuloggen.
    session.pop('user_data', None) # das None sorgt dafür, dass kein Fehler kommt, wenn der Key nicht existiert.
    session.pop('liked_products', None)
    flash("Ausgeloggt!", "success") # Erfolgsmeldung.
    return redirect(url_for('index')) # Zur Startseite umleiten.






# Home-Seite für eingeloggte User.
# Erwartet: Der User muss eingeloggt sein (Prüfung über die Session).
# Gibt weiter: Rendert die 'home.html' mit dem Usernamen, damit der User seine persönliche Startseite sieht.
# Wenn nicht eingeloggt, wird der User zum Login umgeleitet und bekommt eine Warnung.
@app.route('/home')
def home():
    if 'user_data' in session: # Prüfen, ob User eingeloggt ist.
        user_data = session['user_data'] # Usernamen holen.
        return render_template('home.html', user_data=user_data) # 'home.html' anzeigen mit Usernamen.
    else:
        flash("Bitte einloggen!", "warning") # Wenn nicht, Fehlermeldung.
        return redirect(url_for('login')) # Zum Login umleiten.


# Profilseite des Users.
# Erwartet: User muss eingeloggt sein (Session wird geprüft).
# Gibt weiter: Rendert die 'profile.html' und übergibt die Userdaten sowie alle Produkte, die der User gelikt hat.
# Zeigt dem User also sein Profil und seine Favoriten an.
@app.route('/profile')
def profile():
    if 'user_data' not in session: # Prüfen, ob User eingeloggt ist.
        flash("Bitte einloggen!", "warning")
        return redirect(url_for('login')) # Wenn nicht, zum Login.
    
    user = db_user.query.filter_by(username=session['user_data']).first() # User-Daten aus DB holen.
    # Alle gelikten Produkte des Users holen.
    liked_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]

    return render_template('profile.html', user=user, liked_products=liked_products) # Profilseite anzeigen.


# Favoriten-Seite für eingeloggte User.
# Erwartet: User muss eingeloggt sein (Session wird geprüft).
# Gibt weiter: Holt alle Produkte, die der User gelikt hat, aus der Datenbank und vergleicht sie mit den Produkten aus der externen API.
# Rendert dann die 'favorites.html' mit den detaillierten Produktinfos der Favoriten.
# Wenn der User nicht eingeloggt ist, wird er zum Login umgeleitet.
@app.route('/favorites')
def favorites():
    if 'user_data' not in session: # Prüfen, ob User eingeloggt ist.
        flash("Bitte einloggen!", "warning")
        return redirect(url_for('login')) # Wenn nicht, zum Login.
    
    user = db_user.query.filter_by(username=session['user_data']).first() # User-Daten holen.
    # Nur die Namen der gelikten Produkte aus der Datenbank holen.
    liked_db_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]

    try:
        # Produkte von externer API holen (hier DummyJSON, limitiert auf 20).
        response = requests.get("https://dummyjson.com/products?limit=20")
        response.raise_for_status() # Fehler werfen, wenn HTTP-Statuscode schlecht ist.
        api_get_all_products = response.json().get("products", []) # JSON parsen und Produkte holen.
    except requests.exceptions.RequestException as e:
        flash(f"API-Fehler: {e}", "warning") # Fehler bei API-Zugriff.
        return redirect(url_for('home')) # Zur Home-Seite umleiten.
    
    liked_products = [] # Liste für detaillierte gelikte Produkte.
    # Nur die Produkte von der API filtern, die der User auch wirklich gelikt hat.
    for product in api_get_all_products:
        if product["title"] in liked_db_products:
            liked_products.append(product) # Wenn gelikt, das ganze Produkt-Objekt hinzufügen.

    return render_template('favorites.html', user=user, liked_products=liked_products) # Favoriten-Seite anzeigen.


# Debug-Route: Zeigt Session-Daten als JSON. Nur für Entwicklung!
@app.route('/debug-session')
def debug_session_view():
    return jsonify(dict(session)) # Session in ein Dictionary umwandeln und als JSON ausgeben.




# Route für die Like-Funktion. Wird per AJAX aufgerufen. Ajax ist eine Technik, um im Hintergrund Daten zu senden und zu empfangen, ohne die Seite neu zu laden.
@app.route('/like', methods=['POST'])
def like():
    data = request.get_json() # JSON-Daten von der Anfrage holen.
    if not data:
        return jsonify(success=False, message="Keine Daten"), 400 # Fehler, wenn keine Daten.
    product_title = data.get('title') # Produkttitel aus den Daten holen.

    if not product_title:
        return jsonify(success=False, message="Fehlender Titel"), 400 # Fehler, wenn Titel fehlt.

    current_username = session['user_data'] # Aktuellen Usernamen holen.
    liked_in_session = session.get('liked_products', []) # Gelikte Produkte aus Session holen.

    # Prüfen, ob Produkt schon in DB gelikt ist.
    existing_db_like = db_liked_product.query.filter_by(username=current_username, product=product_title).first() #first() gibt das erste gefundene Ergebnis zurück oder None, wenn nichts gefunden wurde.
    if existing_db_like:
        flash(f'"{product_title}" ist schon in Favoriten.', 'warning') # Info-Meldung.
        # Sicherstellen, dass es auch in der Session ist.
        if product_title not in liked_in_session:
            liked_in_session.append(product_title)
            session['liked_products'] = liked_in_session
    else:
        # Produkt neu liken (in DB und Session).
        new_db_like = db_liked_product(username=current_username, product=product_title) # Nimmt den Usernamen und Produkttitel als Parameter.
        db.session.commit()
        if product_title not in liked_in_session:
            liked_in_session.append(product_title)
            session['liked_products'] = liked_in_session
        flash(f'"{product_title}" zu Favoriten hinzugefügt!', 'success') # Erfolgsmeldung.
    
    return jsonify(success=True, message=f"Like für {product_title} aktualisiert."), 200 # JSON-Antwort zurück.


# Route für die Unlike-Funktion. Wird per POST-Anfrage aufgerufen.
@app.route('/unlike', methods=['POST'])
def unlike():
    current_username = session.get('user_data') # Aktuellen Usernamen holen.
    if not current_username:
        flash("Nicht eingeloggt!", "danger")
        return redirect(url_for('login')) # Wenn nicht eingeloggt, zum Login.

    product_to_unlike = request.form.get('title') # Produkttitel aus Formular holen.
    liked = session.get('liked_products', []) # Gelikte Produkte aus Session holen.

    if not product_to_unlike:
        flash("Kein Produkt angegeben", "warning")
        return redirect(url_for('favorites')) # Wenn kein Produkt, zurück zu Favoriten.
    
    # Produkt aus DB löschen.
    db_product_entry = db_liked_product.query.filter_by(username=current_username, product=product_to_unlike).first() #first() gibt das erste gefundene Ergebnis zurück oder None, wenn nichts gefunden wurde.
    #wenn das Produkt in der DB existiert, löschen.
    if db_product_entry:
        db.session.delete(db_product_entry)
        db.session.commit()
        flash(f'"{product_to_unlike}" nicht mehr favorisiert.', 'success') # Erfolgsmeldung.

        # Auch aus Session entfernen.
        if product_to_unlike in liked:
            liked.remove(product_to_unlike)
            session['liked_products'] = liked
            session.modified = True # Wichtig: Session als geändert markieren! Dmait Flask weiß, dass sie gespeichert werden muss.
    else:
        flash(f'"{product_to_unlike}" nicht in Favoriten.', 'warning') # Warnung, wenn nicht gefunden.

    return redirect(url_for('favorites')) # Zurück zu Favoriten.


# Startet die Flask-App.
if __name__ == '__main__':
    with app.app_context(): # Erstellt einen App-Kontext, wichtig für DB-Operationen beim Start.
        db.create_all() # Erstellt alle DB-Tabellen, falls sie noch nicht existieren.
    app.run(debug=True) # Startet den Server im Debug-Modus (Fehleranzeige, Auto-Reload). Im echten Betrieb auf False setzen!
