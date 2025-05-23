from datetime import datetime
from flask import Flask, session, redirect, url_for, request, jsonify, flash, render_template
from flask_sqlalchemy import SQLAlchemy



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
    product = data.get('title')

    liked = session.get('liked_products', [])
    
    if product not in liked:
        liked.append(product)
        session['liked_products'] = liked
        db.session.add(db_liked_product(username=session['user_data'], product=product))
        db.session.commit()
        flash(f'{product} Das Produkt wurde von dir gespeichert', 'success')
    return jsonify(success=True), 200


# Produkt - Unlike Route
@app.route('/unlike', methods=['POST'])
def unlike():

    data = request.get_json()
    product = data.get('title')

    liked = session.get('liked_products', [])
    if product in liked:
        liked.remove(product)
        session['liked_products'] = liked
        db_liked_product.query.filter_by(username=session['user_data'], product=product).delete()
        db.session.commit()
        flash(f'Das Produkt {product} wurde von dir entfernt', 'success')
    return jsonify(success=True), 200





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

    response = request.get("https://dummyjson.com/products?limit=20")
    api_get_all_products = response.json().get("products", [])
    liked_products = []
    for product in api_get_all_products:
        if product["title"] in liked_db_products:
            liked_products.append(product)



    return render_template('favorites.html', user=user, liked_products=liked_products)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
    