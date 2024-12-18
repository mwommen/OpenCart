// Allow insecure transport (HTTP) for development // Set your publishable key from Stripe
const stripe = Stripe('pk_test_bljpr6qrPgJiftEYuLKIJuZh00domXNg3A'); // Replace with your actual Stripe publishable key

// Set up elements for handling the payment form
const elements = stripe.elements();

// Create the card element
const card = elements.create('card');
card.mount('#card-element');

// Handle real-time validation errors from the card element
card.on('change', (event) => {
    const errorDisplay = document.getElementById('card-errors');
    if (event.error) {
        errorDisplay.textContent = event.error.message;
    } else {
        errorDisplay.textContent = '';
    }
});


// Fetch cart items
async function getCartItems() {
    try {
        const response = await fetch('/api/cart');
        const cartItems = await response.json();
        return cartItems.cart_items || [];
    } catch (error) {
        console.error('Error fetching cart items:', error);
        return [];
    }
}

// Show loading indicator
function showLoading() {
    document.getElementById('loading-message').classList.remove('d-none');
}

// Hide loading indicator
function hideLoading() {
    document.getElementById('loading-message').classList.add('d-none');
}

// Handle form submission
async function handleFormSubmit(event) {
    event.preventDefault();
    showLoading();

    // Retrieve cart items
    const cartItems = await getCartItems();

    // Create payment method with Stripe
    const { error, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: card,
        billing_details: {
            name: document.getElementById('name').value,
            email: document.getElementById('email').value,
        },
    });

    if (error) {
        hideLoading();
        displayError(error.message);
    } else {
        // Send payment method and cart data to the server
        try {
            const response = await fetch('/pay', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    paymentMethodId: paymentMethod.id,
                    cartItems: cartItems,
                }),
            });

            const data = await response.json();

            if (data.error) {
                hideLoading();
                displayError(data.error);
            } else {
                // Confirm the payment intent on the client side
                const result = await stripe.confirmPayment({
                    clientSecret: data.clientSecret,
                });

                hideLoading();

                if (result.error) {
                    displayError(result.error.message);
                } else {
                    if (result.paymentIntent.status === 'succeeded') {
                        displaySuccess('Payment successful!');
                        window.location.href = '/payment-success';
                    }
                }
            }
        } catch (serverError) {
            hideLoading();
            displayError('There was an error processing your payment.');
        }
    }
}

// Display error message
function displayError(message) {
    const errorMessage = document.getElementById('error-message');
    errorMessage.classList.remove('d-none');
    errorMessage.textContent = message;
}

// Display success message
function displaySuccess(message) {
    const successMessage = document.getElementById('success-message');
    successMessage.classList.remove('d-none');
    successMessage.textContent = message;
}

// Attach event listener to the form
const form = document.getElementById('payment-form');
form.addEventListener('submit', handleFormSubmit);

// PaymentRequest API setup
const paymentRequest = stripe.paymentRequest({
    country: 'US',
    currency: 'usd',
    total: {
        label: 'Total Amount',
        amount: 5000, // Default value: $50.00 in cents
    },
    requestPayerName: true,
    requestPayerEmail: true,
});

const paymentRequestButton = elements.create('paymentRequestButton', {
    paymentRequest: paymentRequest,
});

// Check if PaymentRequest is available
paymentRequest.canMakePayment().then((result) => {
    if (result) {
        document.getElementById('payment-request-button').style.display = 'block';
        paymentRequestButton.mount('#payment-request-button');
    } else {
        document.getElementById('payment-request-button').style.display = 'none';
    }
});

// Handle PaymentRequest event
paymentRequest.on('paymentmethod', async (ev) => {
    showLoading();
    try {
        const cartItems = await getCartItems();

        const response = await fetch('/pay', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                paymentMethodId: ev.paymentMethod.id,
                cartItems: cartItems,
            }),
        });

        const data = await response.json();

        if (data.error) {
            ev.complete('fail');
            hideLoading();
            alert(data.error);
        } else {
            const result = await stripe.confirmPayment({
                clientSecret: data.clientSecret,
                paymentMethod: ev.paymentMethod.id,
            });

            hideLoading();

            if (result.error) {
                ev.complete('fail');
                alert(result.error.message);
            } else {
                ev.complete('success');
                if (result.paymentIntent.status === 'succeeded') {
                    window.location.href = '/payment-success';
                }
            }
        }
    } catch (error) {
        ev.complete('fail');
        hideLoading();
        alert('Error processing payment.');
    }
});
