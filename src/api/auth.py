"""
Telegram Mini App authentication.
Validates initData using HMAC-SHA256 as per Telegram WebApp docs.
"""
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Header, Depends
from pydantic import BaseModel

from src.config import config


class TelegramUser(BaseModel):
    """Telegram user data from initData."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    photo_url: Optional[str] = None


class AuthData(BaseModel):
    """Parsed and validated auth data."""
    user: TelegramUser
    auth_date: datetime
    query_id: Optional[str] = None
    hash: str


def validate_init_data(init_data: str, bot_token: str) -> AuthData:
    """
    Validate Telegram WebApp initData.

    Algorithm (from Telegram docs):
    1. Parse initData as URL query string
    2. Sort key=value pairs alphabetically
    3. Create data_check_string (excluding hash)
    4. Compute secret_key = HMAC-SHA256("WebAppData", bot_token)
    5. Compute hash = HMAC-SHA256(secret_key, data_check_string)
    6. Compare with received hash

    Returns:
        AuthData with parsed user info

    Raises:
        HTTPException if validation fails
    """
    try:
        # Parse URL-encoded initData
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))

        if "hash" not in parsed:
            raise HTTPException(status_code=401, detail="Missing hash in initData")

        received_hash = parsed.pop("hash")

        # Sort and create data_check_string
        data_check_pairs = sorted(parsed.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_pairs)

        # Compute secret key: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Compute hash: HMAC-SHA256(secret_key, data_check_string)
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify hash
        if not hmac.compare_digest(computed_hash, received_hash):
            raise HTTPException(status_code=401, detail="Invalid initData signature")

        # Check auth_date (not older than 24 hours)
        auth_date_ts = int(parsed.get("auth_date", 0))
        if auth_date_ts == 0:
            raise HTTPException(status_code=401, detail="Missing auth_date")

        auth_date = datetime.fromtimestamp(auth_date_ts)
        if datetime.now() - auth_date > timedelta(hours=24):
            raise HTTPException(status_code=401, detail="initData expired")

        # Parse user JSON
        user_json = parsed.get("user")
        if not user_json:
            raise HTTPException(status_code=401, detail="Missing user in initData")

        user_data = json.loads(user_json)
        user = TelegramUser(**user_data)

        return AuthData(
            user=user,
            auth_date=auth_date,
            query_id=parsed.get("query_id"),
            hash=received_hash
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid user JSON in initData")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid initData: {str(e)}")


async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data")
) -> TelegramUser:
    """
    FastAPI dependency to get current user from initData header.

    Usage:
        @app.get("/api/items")
        async def get_items(user: TelegramUser = Depends(get_current_user)):
            return await fetch_items(user.id)
    """
    auth_data = validate_init_data(x_telegram_init_data, config.telegram.bot_token)
    return auth_data.user


async def get_user_id(
    user: TelegramUser = Depends(get_current_user)
) -> int:
    """
    FastAPI dependency to get just the user ID.

    Usage:
        @app.get("/api/items")
        async def get_items(user_id: int = Depends(get_user_id)):
            return await fetch_items(user_id)
    """
    return user.id
