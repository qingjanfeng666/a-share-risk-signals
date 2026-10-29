"""Email/password login backed by revocable HttpOnly cookie sessions."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from backend.config import FRONTEND_ORIGINS, SESSION_COOKIE_SECURE
from backend.services import email_delivery
from backend.storage import accounts


router = APIRouter(prefix="/api/auth")


class Credentials(BaseModel):
    email: str
    password: str


class Verification(BaseModel):
    email: str
    code: str


def require_trusted_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in FRONTEND_ORIGINS:
        raise HTTPException(status_code=403, detail="请求来源不被允许。")


def require_user(request: Request):
    user = accounts.read_session(request.cookies.get(accounts.SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def _set_session_cookie(response: Response, user_id: int):
    response.set_cookie(
        key=accounts.SESSION_COOKIE,
        value=accounts.create_session(user_id),
        max_age=accounts.SESSION_MAX_AGE,
        path="/",
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )


@router.post("/register", dependencies=[Depends(require_trusted_origin)])
def register(credentials: Credentials):
    if not email_delivery.is_configured():
        raise HTTPException(status_code=503, detail="邮件服务尚未配置，暂时无法注册。")
    try:
        email, code, code_hash = accounts.start_registration(credentials.email, credentials.password)
    except accounts.DuplicateEmailError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except accounts.RateLimitedError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        email_delivery.send_verification_code(email, code)
    except Exception as error:
        accounts.cancel_registration(email, code_hash)
        raise HTTPException(status_code=503, detail="验证码发送失败，请稍后重试。") from error
    return {"status": "code_sent", "email": email}


@router.post("/verify", dependencies=[Depends(require_trusted_origin)])
def verify(verification: Verification, request: Request, response: Response):
    try:
        user = accounts.complete_registration(verification.email, verification.code)
    except accounts.RateLimitedError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except accounts.DuplicateEmailError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except accounts.InvalidVerificationCodeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    accounts.revoke_session(request.cookies.get(accounts.SESSION_COOKIE))
    _set_session_cookie(response, user["id"])
    return user


@router.post("/login", dependencies=[Depends(require_trusted_origin)])
def login(credentials: Credentials, request: Request, response: Response):
    try:
        user = accounts.authenticate(
            credentials.email, credentials.password,
            request.client.host if request.client else "unknown",
        )
    except accounts.RateLimitedError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except accounts.InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    accounts.revoke_session(request.cookies.get(accounts.SESSION_COOKIE))
    _set_session_cookie(response, user["id"])
    return user


@router.get("/me")
def me(user=Depends(require_user)):
    return user


@router.post("/logout", dependencies=[Depends(require_trusted_origin)])
def logout(request: Request, response: Response):
    accounts.revoke_session(request.cookies.get(accounts.SESSION_COOKIE))
    response.delete_cookie(accounts.SESSION_COOKIE, path="/")
    return {"status": "ok"}
