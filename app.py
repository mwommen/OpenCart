from flask import Flask, render_template, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
import stripe

app = Flask(__name__, static_folder='static')
app.secret_key = b"o]\x93$\x81\xcb\xa2_\x99lAo\xd35|\x0f\x13#7x0:\x8d'"
CORS(app)

# Initialize Stripe
stripe.api_key = "sk_test_eoYbAa1iA0dXvyo49ECeclx90042N7R0jA"

# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='1032661561845-jcg5ugk64st7frpb2g9j4t3phdcedcch.apps.googleusercontent.com',  # Replace with your Google Client ID
    client_secret='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',  # Replace with your Google Client Secret
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid profile'},  # Add the scope here
)

# Routes
@app.route('/')
def index():
    user_email = session.get('user_email')
    return render_template('index.html', user_email=user_email)

@app.route('/login')
def login():
    return google.authorize_redirect(url_for('oauth2callback', _external=True))

@app.route('/oauth2callback')  # Ensure this matches the URI in your Google Console
def oauth2callback():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    session['user_email'] = user_info['email']
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect('/')

@app.route("/create-payment-intent", methods=["POST"])
def create_payment_intent():
    try:
        data = request.get_json()
        amount = sum(item['price'] * item['quantity'] for item in data['cart']['store1']) * 100  # in cents
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
        )
        return jsonify({"client_secret": intent.client_secret})
    except Exception as e:
        return jsonify(error=str(e)), 400

if __name__ == "__main__":
    app.run(debug=True, port=8000)
