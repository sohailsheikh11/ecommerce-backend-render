
import hashlib
import json
import secrets

from app.core.redis_client import redis_client


OTP_TTL_SECONDS = 300


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def save_pending_signup(
    email: str,
    name: str,
    hashed_password: str,
    otp: str,
) -> None:
    key = f"pending_signup:{email.lower()}"

    signup_data = {
        "email": email.lower(),
        "name": name,
        "hashed_password": hashed_password,
        "otp_hash": hash_otp(otp),
    }

    redis_client.set(
        key,
        json.dumps(signup_data),
        ex=OTP_TTL_SECONDS,
    )


def get_pending_signup(email: str) -> dict | None:
    key = f"pending_signup:{email.lower()}"

    data = redis_client.get(key)

    if data is None:
        return None

    return json.loads(data)


def delete_pending_signup(email: str) -> None:
    key = f"pending_signup:{email.lower()}"
    redis_client.delete(key)
