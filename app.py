from datetime import datetime
from flask import Flask, session, redirect, url_for, request, jsonify, flash, render_template
from flask_sqlalchemy import SQLAlchemy
import requests



app = Flask(__name__)
app.secret_key = 'secret_key_project'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the SQLAlchemy object | Damit kennt die App die Datenbank
db = SQLAlchemy(app)


# Datenbank-Modell für Benutzer | alle Felder sind pflicht
class db_user(db.Model):
    _id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    creation = db.Column(db.DateTime, default=datetime.now)
    country = db.Column(db.String(150), nullable=True)

    def __init__(self, username, password, email, country):
        self.username = username
        self.password = password
        self.email = email
        self.country = country



class db_liked_product(db.Model):
    _id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    product = db.Column(db.String(150), nullable=False)



# Funktion um die Anzahl der Benutzer zu zählen
@app.context_processor
def inject_user_count():
    return {"user_count": db_user.query.count()}



# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        email = request.form['email']
        password = request.form['password']
        country = request.form['country']

        if db_user.query.filter_by(email=email).first():
            flash("Diese Email wird schon verwendet ! :(", "warning")
            return redirect(url_for('register'))

        if db_user.query.filter_by(username=user).first():
            flash("Dieser Benutzername wird schon verwendet ! :( ", "warning")
            return redirect(url_for('register'))

        new_user = db_user(user, password, email, country)
        db.session.add(new_user)
        db.session.commit()
        flash("Benutzer erfolgreich registriert ! :)", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        user_data = db_user.query.filter_by(username=user).first()

        if user_data and user_data.password == password:
            session['user_data'] = user_data.username
            likes = db_liked_product.query.filter_by(username=user_data.username).all()
            session['liked_products'] = [like.product for like in likes]
            flash("Erfolgreich eingeloggt", "success")
            return redirect(url_for('home'))
        else:
            flash("Benutzername oder Passwort falsch", "warning")
            return redirect(url_for('login'))
    return render_template('login.html')




# Logout Route
@app.route('/logout')
def logout():
    if 'user_data' in session:
        liked_products = session.get('liked_products', [])
        for product in liked_products:
            if not db_liked_product.query.filter_by(username=session['user_data'], product=product).first():
                db.session.add(db_liked_product(username=session['user_data'], product=product))
        db.session.commit()
       
    session.pop('user_data', None)
    session.pop('liked_products', None)
    flash("Erfolgreich ausgeloggt", "success")
    return redirect(url_for('index'))


# Produkt - Like Route

@app.route('/like', methods=['POST'])
def like():
    data = request.get_json()
    # Prüfen, ob überhaupt Daten gesendet wurden und ob der Titel da ist
    if not data:
        return jsonify(success=False, message="No data provided"), 400  # Bad Request
    product_title = data.get('title')

    if not product_title:
        return jsonify(success=False, message="No product title provided"), 400

    current_username = session['user_data']
    liked_in_session = session.get('liked_products', [])  # Deine bestehende Session-Logik

    # Prüfen, ob das Produkt bereits in der DATENBANK für diesen Nutzer existiert
    existing_db_like = db_liked_product.query.filter_by(username=current_username, product=product_title).first()
    if existing_db_like:
        # Produkt ist bereits in der Datenbank geliked
        flash(f'"{product_title}" ist bereits in deinen Favoriten.', 'info')
        if product_title not in liked_in_session:
            liked_in_session.append(product_title)
            session['liked_products'] = liked_in_session
    else:
        # Produkt ist noch nicht in der Datenbank für diesen Nutzer -> Hinzufügen
        new_db_like = db_liked_product(username=current_username, product=product_title)
        db.session.add(new_db_like)
        db.session.commit()
        flash(f'"{product_title}" wurde zu deinen Favoriten hinzugefügt!', 'success')
    
    return jsonify(success=True, message=f"Like status for {product_title} updated."), 200


# Produkt - Unlike Route
@app.route('/unlike', methods=['POST'])
def unlike():

    product_to_unlike = request.form.get('title')
    

    liked = session.get('liked_products', [])

    if not product_to_unlike:
        flash("Kein Produkt angegeben", "warning")
        return redirect(url_for('favorites'))
    
 
    db_product_entry = db_liked_product.query.filter_by(username=session['user_data'], product=product_to_unlike).first()
    if not db_product_entry:
        
        flash(f'Das Produkt {product_to_unlike} konnte nicht entfernt werden.', 'warning')
    elif db_product_entry:
        liked.remove(product_to_unlike)
        session['liked_products'] = liked
        db.session.delete(db_product_entry)
        db.session.commit()
        flash(f'Das Produkt {product_to_unlike} wurde von dir entfernt', 'success')
    
    return redirect(url_for('favorites'))





# Index Route
@app.route('/')
def index():
    return render_template('index.html')


# Home Route 

@app.route('/home')
def home():
    if 'user_data' in session:
        user_data = session['user_data']

        return render_template('home.html', user_data=user_data)
    else:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))

# Profile Route
@app.route('/profile')
def profile():
    if 'user_data' not in session:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))
    
    user = db_user.query.filter_by(username=session['user_data']).first()
    # Hier werden NUR die Produktnamen extrahiert!
    liked_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]

    return render_template('profile.html', user=user, liked_products=liked_products)

#Favoriten Route 
@app.route('/favorites')
def favorites():
    if 'user_data' not in session:
        flash("Bitte zuerst einloggen", "warning")
        return redirect(url_for('login'))
    
    user = db_user.query.filter_by(username=session['user_data']).first()
    liked_db_products = [like.product for like in db_liked_product.query.filter_by(username=user.username).all()]
    try:
        response = requests.get("https://dummyjson.com/products?limit=100")
        response.raise_for_status()  # Raise an error for bad responses
        api_get_all_products = response.json().get("products", [])
    except requests.exceptions.RequestException as e:
        flash("Fehler beim Abrufen der Produktdaten {e}", "warning")
        return redirect(url_for('home'))
    
    # Hier werden NUR die Produktnamen extrahiert!
    liked_products = []
    for product in api_get_all_products:
        if product["title"] in liked_db_products:
            liked_products.append(product)



    return render_template('favorites.html', user=user, liked_products=liked_products)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
