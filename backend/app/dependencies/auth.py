import logging
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWKS client — fetches Supabase's public keys and caches them for 5 minutes.
# Handles ES256 (Supabase's default) without needing the raw JWT secret.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_uri = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300)
    return _jwks_client


def _decode(token: str) -> dict:
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256", "HS256"],
        audience="authenticated",
    )


def _claims_to_user(payload: dict) -> dict:
    return {
        "id": payload.get("sub"),
        "email": payload.get("email", ""),
        "role": payload.get("role", "authenticated"),
        "name": (payload.get("user_metadata") or {}).get("full_name")
            or (payload.get("user_metadata") or {}).get("name")
            or (payload.get("email") or "").split("@")[0],
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        return _claims_to_user(_decode(credentials.credentials))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
    except Exception as exc:
        logger.error("Token verification error: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed")


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[dict]:
    if not credentials:
        return None
    try:
        return _claims_to_user(_decode(credentials.credentials))
    except Exception:
        return None


async def verify_websocket_token(token: str) -> dict:
    try:
        return _claims_to_user(_decode(token))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
    except Exception as exc:
        logger.error("WS token verification error: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed")
