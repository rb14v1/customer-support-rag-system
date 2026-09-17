from fastapi import Header, HTTPException


def authenticate(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )