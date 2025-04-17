from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends, Header, HTTPException, status

from passlib.context import CryptContext
from datetime import UTC, datetime, timedelta

import jwt
from typing import Optional, Union, List, Dict


ALGORITHM = "HS256"

bearer_security = HTTPBearer(auto_error=False)


def get_verify_api_key(api_key: str):
    async def verify_api_key(
        authorization: HTTPAuthorizationCredentials = Depends(bearer_security),
    ):
        if not authorization or not authorization.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = authorization.credentials
        if token != api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

    return verify_api_key


# def create_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
#     payload = data.copy()

#     if expires_delta:
#         expire = datetime.now(UTC) + expires_delta
#         payload.update({"exp": expire})

#     encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
#     return encoded_jwt


# def decode_token(token: str) -> Optional[dict]:
#     try:
#         decoded = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
#         return decoded
#     except Exception:
#         return None
