import os
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import stripe
from oauthlib.oauth2 import WebApplicationClient
import requests
import time  # Importing time here
import base64 
import xml.etree.ElementTree as ET
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

import os
print(os.getenv('UPS_CLIENT_ID'))
print(os.getenv('UPS_CLIENT_SECRET'))


# Initialize Flask app and configuration
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # Default for local testing
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
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    mobile_number = db.Column(db.String(20), nullable=True)
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    postcode = db.Column(db.String(10), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    area = db.Column(db.String(100), nullable=True)
    education = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<User {self.email}>'


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
    # Fetch products from WooCommerce API
    API_URL = "https://ecom-superbly-warm-tidalwave.wpcomstaging.com/wp-json/wc/v3/products"
    CONSUMER_KEY = os.getenv("CONSUMER_KEY")
    CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")

    response = requests.get(API_URL, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    products = []

    if response.status_code == 200:
        products = response.json()  # Get products data
    else:
        print(f"Failed to fetch products. HTTP Status Code: {response.status_code}")
    
    return render_template('index.html', products=products)

# Route for the profile page
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_email = session.get('user_email')
    
    if not user_email:
        return redirect(url_for('login'))  # If not logged in, redirect to login
    
    user = User.query.filter_by(email=user_email).first()  # Fetch the user from the database
    
    if request.method == 'POST':
        # Update the user's profile data
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.mobile_number = request.form.get('mobile_number')
        user.address_line1 = request.form.get('address_line1')
        user.address_line2 = request.form.get('address_line2')
        user.postcode = request.form.get('postcode')
        user.state = request.form.get('state')
        user.area = request.form.get('area')
        user.education = request.form.get('education')

        # Commit changes to the database
        db.session.commit()
        return redirect(url_for('profile'))  # Redirect to the profile page after saving changes

    # Render the profile page with the current data
    return render_template('profile.html', user=user)




# Login route (Redirects to Google OAuth)
@app.route('/login')
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    
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
        code = request.args.get("code")
        
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
        
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        userinfo_response = requests.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {client.token['access_token']}"}
        )
        user_info = userinfo_response.json()
        
        session['user_email'] = user_info.get("email")
        print(f"User logged in: {session['user_email']}")
        return redirect(url_for("index"))
    except Exception as e:
        return jsonify({"error": f"OAuth Callback failed: {str(e)}"}), 500

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('index'))

# Route to retrieve the cart data
@app.route('/api/cart', methods=['GET'])
def get_cart():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    cart = Cart.query.filter_by(user_email=user_email).first()
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

    cart = Cart.query.filter_by(user_email=user_email).first()
    if not cart:
        cart = Cart(user_email=user_email)
        db.session.add(cart)
        db.session.commit()

    new_item = CartItem(
        product_name=product_name,
        quantity=quantity,
        price=price,
        cart_id=cart.id
    )
    db.session.add(new_item)
    db.session.commit()

    return jsonify({"message": "Item added successfully"})

# Pay route
@app.route('/pay', methods=['POST'])
def pay():
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "User not logged in"}), 401

        cart = Cart.query.filter_by(user_email=user_email).first()
        if not cart or not cart.items:
            return jsonify({"error": "No cart items found"}), 404

        total_amount = sum(item.quantity * item.price for item in cart.items)

        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),
            currency='usd',
            automatic_payment_methods={'enabled': True},
        )

        return jsonify({"clientSecret": intent.client_secret})
    except Exception as e:
        return jsonify({"error": str(e)}), 403

if __name__ == "__main__":
    with app.app_context():
        db.create_all()




# Get the USPS API key (USERID) from .env
usps_userid = os.getenv('USPS_USERID')

if not usps_userid:
    raise ValueError("USPS_USERID is not set in the environment variables")

def track_package(tracking_number):
    """
    Function to track a package using the USPS API.
    Args:
        tracking_number (str): The tracking number of the package.
    Returns:
        str: Response from the USPS API (XML format).
    """
    url = "https://secure.shippingapis.com/ShippingAPI.dll"
    
    # Define the XML request data
    request_data = f"""
    <TrackRequest USERID="{usps_userid}">
        <TrackID ID="{tracking_number}"></TrackID>
    </TrackRequest>
    """
    
    # Set up the request parameters
    params = {
        "API": "TrackV2",
        "XML": request_data
    }

    try:
        # Send the request to USPS
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        return response.text  # Return the response as XML
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        return f"An error occurred: {e}"

# Example usage
if __name__ == "__main__":
    tracking_number = "9205 5000 0000 0000 0000 00"  # Replace with an actual tracking number
    tracking_info = track_package(tracking_number)
    print(tracking_info)












# Retrieve credentials from environment variables
UPS_CLIENT_ID = os.getenv('UPS_CLIENT_ID')
UPS_CLIENT_SECRET = os.getenv('UPS_CLIENT_SECRET')
UPS_TRACKING_URL = "https://onlinetools.ups.com/rest/Track"

print(UPS_CLIENT_ID)
print(UPS_CLIENT_SECRET)

access_token = None
token_expiry = None

def get_ups_access_token():
    """Authenticate with UPS and get the access token."""
    global access_token, token_expiry

    # Return the cached token if it's still valid
    if access_token and token_expiry and time.time() < token_expiry:
        return access_token

    if not UPS_CLIENT_ID or not UPS_CLIENT_SECRET:
        print("Error: Missing UPS credentials.")
        return None

    # Encode client_id and client_secret for the Authorization header
    client_credentials = f"{UPS_CLIENT_ID}:{UPS_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(client_credentials.encode('utf-8')).decode('utf-8')

    # The API URL for UPS authentication (testing environment)
    auth_url = "https://wwwcie.ups.com/security/v1/oauth/token"

    # Prepare the headers for the POST request
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'accept': 'application/json'
    }

    # Prepare the data for the POST request using the form data format
    auth_payload = {
        'grant_type': 'client_credentials'
    }

    # Make the authentication request
    response = requests.post(auth_url, data=auth_payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        access_token = data.get('access_token')
        # Set the token expiry (assuming the token is valid for 1 hour)
        token_expiry = time.time() + 3600  # Adjust based on your token's expiration time
        return access_token
    else:
        print(f"Error getting access token: {response.status_code} - {response.text}")
        return None

@app.route('/track_package', methods=['POST'])
def track_package():
    tracking_number = request.form.get('tracking_number')

    if not tracking_number:
        return jsonify({"error": "Tracking number is required"}), 400

    # Get UPS OAuth access token
    access_token = get_ups_access_token()

    if not access_token:
        return jsonify({"error": "Failed to authenticate with UPS API"}), 500

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    # Prepare payload for UPS Tracking API
    payload = {
        "trackingNumber": [tracking_number]
    }

    # Make the API request
    response = requests.post(UPS_TRACKING_URL, json=payload, headers=headers)

    if response.status_code == 200:
        tracking_info = response.json()

        if 'trackResponse' in tracking_info:
            return jsonify({"tracking_info": tracking_info['trackResponse']})
        else:
            return jsonify({"error": "Invalid tracking number or no information found"}), 404
    else:
        error_message = response.json().get("response", {}).get("errors", [{}])[0].get("message", "Unknown error")
        print(f"Error from UPS: {error_message}")  # Log error for debugging
        return jsonify({"error": f"Failed to track package: {error_message}"}), response.status_code

if __name__ == '__main__':
    app.run(debug=True, port=8000)