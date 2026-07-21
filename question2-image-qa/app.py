"""NovaCorp multimodal image question-answering API."""

from __future__ import annotations

import base64
import binascii
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


app = FastAPI(title="NovaCorp Image QA API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImageQuestion(BaseModel):
    image_base64: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2_000)


class ImageAnswer(BaseModel):
    answer: str


def decode_image(value: str) -> tuple[bytes, str]:
    """Decode standard or data-URL base64 and identify a supported image type."""
    try:
        image = base64.b64decode(value.split(",", 1)[-1].strip(), validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "image_base64 must be valid base64") from error
    if not image or len(image) > 10 * 1024 * 1024:
        raise HTTPException(422, "image must be between 1 byte and 10 MB")
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return image, "image/png"
    if image.startswith(b"\xff\xd8\xff"):
        return image, "image/jpeg"
    if image.startswith((b"GIF87a", b"GIF89a")):
        return image, "image/gif"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return image, "image/webp"
    raise HTTPException(422, "image must be PNG, JPEG, GIF, or WebP")


@app.post("/answer-image", response_model=ImageAnswer)
def answer_image(request: ImageQuestion) -> ImageAnswer:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(503, "GEMINI_API_KEY is not configured")

    image, mime_type = decode_image(request.image_base64)
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60_000),
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash"),
            contents=[
                types.Part.from_bytes(data=image, mime_type=mime_type),
                "Read the image and answer the question accurately. Return only the answer: "
                "no explanation, label, unit, or currency symbol. For a numeric answer, "
                "return only the displayed number.\nQuestion: " + request.question,
            ],
        )
    except Exception as error:
        raise HTTPException(502, "Gemini image analysis failed") from error

    answer = (response.text or "").strip().strip('"')
    if not answer:
        raise HTTPException(502, "Gemini returned an empty answer")
    return ImageAnswer(answer=answer)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
