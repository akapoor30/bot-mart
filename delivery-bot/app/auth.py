from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError, jwt
import requests

# Your Keycloak Realm details
KEYCLOAK_URL = "http://localhost:8080/realms/bot-mart"
CERTS_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"
ALGORITHM = "RS256"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_URL}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_URL}/protocol/openid-connect/token",
)

# Fetch public keys from Keycloak to verify the JWT signature locally
def get_keycloak_public_key(token: str):
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = requests.get(CERTS_URL).json()
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token header")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        public_key = get_keycloak_public_key(token)
        # Decode and validate the token
        payload = jwt.decode(token, public_key, algorithms=[ALGORITHM], audience="account")
        
        keycloak_id: str = payload.get("sub")
        email: str = payload.get("email")
        
        if keycloak_id is None:
            raise credentials_exception
            
        return {"keycloak_id": keycloak_id, "email": email}
        
    except JWTError:
        raise credentials_exception