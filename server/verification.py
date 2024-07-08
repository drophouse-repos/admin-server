import os
from fastapi import FastAPI, Depends, HTTPException, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth
from dotenv import load_dotenv
from typing import Optional
import jwt

load_dotenv()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# def verify_id_token(authorization: str = Header(None)):
def verify_id_token(credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()), x_bearer: str = Header(None)):
    if credentials and x_bearer == 'Alumini':
        scheme = credentials.scheme
        token = credentials.credentials
        if not scheme or scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Unauthorized or malformed token")

        try:
            decoded_token = firebase_auth.verify_id_token(token).get("uid")
            return decoded_token
        except firebase_auth.InvalidIdTokenError as e:
            raise HTTPException(status_code=69, detail="Invalid ID token: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying ID token: {e}")
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return payload["user_id"]
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    elif authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

