import base64
from datetime import datetime
import os
import requests
from django.core.exceptions import ImproperlyConfigured


SANDBOX_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_URL = "https://api.safaricom.co.ke"


def get_mpesa_base_url():
    environment = os.getenv("MPESA_ENVIRONMENT", "sandbox").lower()

    if environment == "sandbox":
        return SANDBOX_URL

    if environment == "production":
        return PRODUCTION_URL

    raise ImproperlyConfigured(
        "MPESA_ENVIRONMENT must be sandbox or production."
    )


def get_access_token():
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        raise ImproperlyConfigured(
            "M-Pesa Consumer Key or Consumer Secret is missing."
        )

    url = (
        f"{get_mpesa_base_url()}"
        "/oauth/v1/generate?grant_type=client_credentials"
    )

    try:
        response = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        access_token = data.get("access_token")

        if not access_token:
            raise ValueError("Daraja did not return an access token.")

        return {
            "access_token": access_token,
            "expires_in": data.get("expires_in"),
        }

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not authenticate with Daraja: {error}"
        ) from error

def initiate_stk_push(
    phone_number,
    amount,
    account_reference,
    transaction_desc="Payment"
):
    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    callback_url = os.getenv("MPESA_CALLBACK_URL")

    if not shortcode or not passkey:
        raise ImproperlyConfigured(
            "M-Pesa shortcode or passkey is missing."
        )

    if not callback_url:
        raise ImproperlyConfigured(
            "MPESA_CALLBACK_URL must be configured."
        )

    # Normalize Kenyan phone numbers
    phone = str(phone_number).strip().replace(" ", "").replace("-", "")

    if phone.startswith("+"):
        phone = phone[1:]
    elif phone.startswith("0"):
        phone = "254" + phone[1:]
    elif len(phone) == 9:
        phone = "254" + phone

    if not phone.isdigit() or len(phone) != 12 or not phone.startswith("254"):
        raise ValueError("Enter a valid Kenyan phone number.")

    amount = int(amount)

    if amount < 1:
        raise ValueError("Payment amount must be at least KSh 1.")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    password_string = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(
        password_string.encode("utf-8")
    ).decode("utf-8")

    token_data = get_access_token()
    access_token = token_data["access_token"]

    url = f"{get_mpesa_base_url()}/mpesa/stkpush/v1/processrequest"

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": str(account_reference)[:12],
        "TransactionDesc": str(transaction_desc)[:13],
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        response_data = getattr(error.response, "text", None)
        raise RuntimeError(
            f"STK Push request failed: {response_data or error}"
        ) from error
