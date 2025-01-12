import requests

UPS_CLIENT_ID = "QnFWbAQSf7MI0TGgLAilxCtKzlJFNQpxaW6nQpGRAMghXf6h"
UPS_CLIENT_SECRET = "AfJXgeUl6uqglZOqKoBHRkJNMlGJuN6UQVppOmp4iRZHwBNfTTwhbjS7UEDYuTSP"

auth_url = "https://wwwcie.ups.com/security/v1/oauth/token"  # Test environment URL
headers = {"Content-Type": "application/x-www-form-urlencoded"}
data = {
    "grant_type": "client_credentials",
    "client_id": UPS_CLIENT_ID,
    "client_secret": UPS_CLIENT_SECRET,
}

response = requests.post(auth_url, data=data, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")






