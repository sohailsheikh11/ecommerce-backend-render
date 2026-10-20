import jwt

from app.core.jwt_utils import create_access_token, decode_access_token

token = create_access_token(user_id=1)

print("Token created:", bool(token))

payload = decode_access_token(token)
print("User ID:", payload["sub"])

try:
    decode_access_token("invalid-token")
except jwt.InvalidTokenError:
    print("Invalid token rejected")