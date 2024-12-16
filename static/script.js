const stripe = Stripe("pk_test_bljpr6qrPgJiftEYuLKIJuZh00domXNg3A");
const elements = stripe.elements();
const apiUrl = "/create-payment-intent"; // Set the correct API URL

// Create a card element
const card = elements.create('card', {
    hidePostalCode: true,
    style: {
        base: {
            color: '#32325d',
            fontFamily: 'Arial, sans-serif',
            fontSize: '16px',
            '::placeholder': {
                color: '#aab7c4',
            },
        },
        invalid: {
            color: '#fa755a',
            iconColor: '#fa755a',
        },
    },
});
card.mount('#card-element');

// Handle form submission
const form = document.getElementById('payment-form');
form.addEventListener('submit', async (event) => {
    event.preventDefault();

    // Disable button to prevent multiple submissions
    const submitButton = document.getElementById('submit');
    submitButton.disabled = true;

    // Clear previous messages
    clearMessages();

    try {
        // Example dynamic cart data (you should replace this with real cart data)
        const cartData = {
            cart: {
                store1: [
                    { price: 500, quantity: 2 },
                    { price: 300, quantity: 1 },
                ],
            },
        };

        // Fetch payment intent client secret
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cartData),
        });

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        // Confirm card payment
        const { error } = await stripe.confirmCardPayment(data.client_secret, {
            payment_method: { card },
        });

        if (error) {
            throw new Error(error.message);
        }

        // Payment successful
        showMessage('success', 'Payment successful!');
    } catch (error) {
        // Handle errors
        showMessage('error', error.message);
    } finally {
        // Re-enable the button
        submitButton.disabled = false;
    }
});

// Show success or error messages
function showMessage(type, message) {
    const messageElement = type === 'success' ? document.getElementById('success-message') : document.getElementById('error-message');
    messageElement.textContent = message;
    messageElement.classList.remove('d-none');
}

// Clear previous messages
function clearMessages() {
    document.getElementById('success-message').classList.add('d-none');
    document.getElementById('error-message').classList.add('d-none');
}
