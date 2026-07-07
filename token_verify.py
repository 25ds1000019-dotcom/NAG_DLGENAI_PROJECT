from __future__ import annotations

import base64
import json
import math
import time
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-27wynei1.apps.exam.local"
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""


@dataclass(frozen=True)
class VerifiedToken:
    email: Any
    sub: Any
    aud: Any


class TokenVerificationError(ValueError):
    pass


def _b64url_decode(value: str) -> bytes:
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise TokenVerificationError("invalid base64") from exc


def _decode_json(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_b64url_decode(segment))
    except (ValueError, UnicodeError) as exc:
        raise TokenVerificationError("invalid json") from exc
    if not isinstance(value, dict):
        raise TokenVerificationError("invalid jwt object")
    return value


def verify_jwt(
    token: str,
    *,
    public_key_pem: str = PUBLIC_KEY_PEM,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    now: float | None = None,
) -> VerifiedToken:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenVerificationError("invalid jwt format")

    header = _decode_json(parts[0])
    payload = _decode_json(parts[1])
    if header.get("alg") != "RS256":
        raise TokenVerificationError("invalid algorithm")

    try:
        signature = _b64url_decode(parts[2])
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(
            signature,
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, TypeError, ValueError, UnicodeError) as exc:
        raise TokenVerificationError("invalid signature") from exc

    if payload.get("iss") != issuer:
        raise TokenVerificationError("invalid issuer")
    if payload.get("aud") != audience:
        raise TokenVerificationError("invalid audience")

    exp = payload.get("exp")
    if (
        isinstance(exp, bool)
        or not isinstance(exp, (int, float))
        or (isinstance(exp, float) and not math.isfinite(exp))
        or exp <= (time.time() if now is None else now)
    ):
        raise TokenVerificationError("expired token")

    return VerifiedToken(
        email=payload.get("email"),
        sub=payload.get("sub"),
        aud=payload.get("aud"),
    )
