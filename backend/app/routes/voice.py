"""Voice routes — Sarvam AI speech-to-text and text-to-speech.

POST /api/voice/stt         — multipart audio upload -> {"text": "..."}
POST /api/voice/tts         — {"text": "..."} -> full audio/wav bytes (waits
                               for the whole clip; used nowhere in the UI
                               anymore, kept for anything that wants a
                               complete file rather than a stream)
GET  /api/voice/tts/stream  — ?text=...&token=... -> streamed audio/mpeg.
                               This is what the chat widget's <audio> element
                               points at directly, so playback starts on the
                               first chunk instead of waiting for the full
                               reply to finish synthesizing.
GET  /api/voice/status — whether SARVAM_API_KEY is configured (frontend uses
                          this to decide whether to show the mic button at all)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from .. import voice
from ..auth import get_current_user, get_current_user_allow_query_token
from ..config import settings
from ..schemas import TTSRequest

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/status")
def status(user=Depends(get_current_user)):
    return {"enabled": settings.voice_enabled}


@router.post("/stt")
async def speech_to_text(file: UploadFile, user=Depends(get_current_user)):
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice isn't configured on this server")
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    text = voice.transcribe(audio_bytes, file.filename or "audio.webm", file.content_type or "audio/webm")
    return {"text": text}


@router.post("/tts")
def text_to_speech(body: TTSRequest, user=Depends(get_current_user)):
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice isn't configured on this server")
    audio_bytes = voice.synthesize(body.text)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Nothing to synthesize")
    return Response(content=audio_bytes, media_type="audio/wav")


@router.get("/tts/stream")
def text_to_speech_stream(
    text: str = Query(..., min_length=1, max_length=3500),
    user=Depends(get_current_user_allow_query_token),
):
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice isn't configured on this server")
    gen = voice.synthesize_stream(text)
    try:
        first_chunk = next(gen)
    except StopIteration:
        raise HTTPException(status_code=400, detail="Nothing to synthesize")

    def combined():
        yield first_chunk
        yield from gen

    return StreamingResponse(combined(), media_type="audio/mpeg")
