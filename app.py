import os
# Allow insecure transport (HTTP) for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import stripe
from oauthlib.oauth2 import WebApplicationClient
import requests

# Initialize Flask app and configuration
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # Set default for local testing
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set up Stripe API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_123")

# OAuth2 client setup (Google)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your-google-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your-google-client-secret")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    items = db.relationship('CartItem', backref='cart', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)

# Index route (Home page)
@app.route('/')
def index():
    return render_template('index.html')

# Debug route: View session for troubleshooting
@app.route('/debug')
def debug():
    return jsonify({"session_email": session.get('user_email')})

# Login route (Redirects to Google OAuth)
@app.route('/login')
def login():
    # Get Google provider configuration
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    
    # Generate the Google OAuth login URL
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri="http://127.0.0.1:8000/callback",  # Explicit redirect_uri
        scope=["openid", "profile", "email"]
    )
    return redirect(request_uri)

# Callback route (Handles Google OAuth callback)
@app.route("/callback")
def callback():
    try:
        # Get the authorization code from the request URL
        code = request.args.get("code")
        
        # Fetch the tokens from Google
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=url_for("callback", _external=True),
            code=code
        )
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )
        client.parse_request_body_response(token_response.text)
        
        # Fetch user info from Google
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        userinfo_response = requests.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {client.token['access_token']}"}
        )
        user_info = userinfo_response.json()
        
        # Store user info in session and redirect to index
        session['user_email'] = user_info.get("email")
        print(f"User logged in: {session['user_email']}")
        return redirect(url_for("index"))
    except Exception as e:
        return jsonify({"error": f"OAuth Callback failed: {str(e)}"}), 500

# Logout route (Clear session and redirect to index)
@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('index'))

# Route to retrieve the cart data for a logged-in user
@app.route('/api/cart', methods=['GET'])
def get_cart():
    user_email = session.get('user_email')
    print(f"Retrieving cart for user: {user_email}")  # Debugging output

    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    # Fetch the cart from the database
    cart = Cart.query.filter_by(user_email=user_email).first()
    print(f"Cart found: {cart}")  # Debugging output

    if not cart or not cart.items:
        return jsonify({"error": "No cart data found for this user"}), 404

    cart_data = {
        "user_email": user_email,
        "cart_items": [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "price": item.price
            }
            for item in cart.items
        ]
    }
    return jsonify(cart_data)

# Route to add items to the cart
@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    data = request.json
    product_name = data.get('product_name')
    quantity = data.get('quantity')
    price = data.get('price')

    if not product_name or not quantity or not price:
        return jsonify({"error": "Missing item details"}), 400

    # Find or create the user's cart
    cart = Cart.query.filter_by(user_email=user_email).first()
    if not cart:
        cart = Cart(user_email=user_email)
        db.session.add(cart)
        db.session.commit()

    # Add the item to the cart
    new_item = CartItem(
        product_name=product_name,
        quantity=quantity,
        price=price,
        cart_id=cart.id
    )
    db.session.add(new_item)
    db.session.commit()

    return jsonify({"message": "Item added successfully"})

# Pay route (Handles Stripe payment intent)
@app.route('/pay', methods=['POST'])
def pay():
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "User not logged in"}), 401

        # Retrieve user's cart
        cart = Cart.query.filter_by(user_email=user_email).first()
        if not cart or not cart.items:
            return jsonify({"error": "No cart items found"}), 404

        # Calculate total amount
        total_amount = sum(item.quantity * item.price for item in cart.items)

        # Create a PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),  # Stripe works with cents
            currency='usd',
            automatic_payment_methods={'enabled': True},
        )

        return jsonify({"clientSecret": intent.client_secret})
    except Exception as e:
        return jsonify({"error": str(e)}), 403

if __name__ == "__main__":
    # Create all tables in the database
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=8000)