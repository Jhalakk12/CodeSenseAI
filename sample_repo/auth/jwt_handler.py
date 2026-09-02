import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

SECRET_KEY = "codesense-dev-secret-key-change-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token for authentication.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifies the JWT token and returns payload.
    NOTE: Potential security edge case if algorithm is not strictly validated.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Authentication token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid authentication token")


def refresh_session(token: str) -> str:
    """
    Refreshes an existing valid token for an extended session.
    """
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing user subject")
    return create_access_token({"sub": user_id})
