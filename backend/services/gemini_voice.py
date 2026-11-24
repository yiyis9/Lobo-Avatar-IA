import base64
import logging
import os
import tempfile
from pathlib import Path


logger = logging.getLogger(__name__)
MAX_TRANSCRIPTION_BYTES = 1_000_000
MAX_SPEECH_BYTES = 12_000_000


class VoiceConfigurationError(RuntimeError):
    pass


class VoiceServiceError(RuntimeError):
    pass


def transcribe_wav(audio: bytes) -> str:
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise ValueError("El audio debe estar en formato WAV.")
    if len(audio) > MAX_TRANSCRIPTION_BYTES:
        raise ValueError("La grabación supera el límite permitido.")
    if len(audio) < 44:
        raise ValueError("La grabación está vacía o incompleta.")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VoiceConfigurationError("La función de voz no está configurada.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise VoiceConfigurationError("Instala las dependencias de voz de Gemini.") from error

    uploaded_file = None
    client = genai.Client(api_key=api_key)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio)
            temp_path = Path(temp_file.name)
        uploaded_file = client.files.upload(
            file=str(temp_path),
            config=types.UploadFileConfig(mime_type="audio/wav"),
        )
        interaction = client.interactions.create(
            model=os.getenv("GEMINI_TRANSCRIBE_MODEL", "gemini-3.5-transcribe").strip(),
            input=[{"type": "audio", "uri": uploaded_file.uri, "mime_type": "audio/wav"}],
            generation_config={"transcription_config": {"language_codes": ["es-MX"]}},
            store=False,
        )
        transcript = (interaction.output_text or "").strip()
        if not transcript:
            raise VoiceServiceError("No se reconoció voz clara en la grabación.")
        return transcript[:1000]
    except VoiceServiceError:
        raise
    except Exception as error:
        logger.warning("Gemini no pudo transcribir el audio", exc_info=True)
        raise VoiceServiceError("No se pudo transcribir el audio. Intenta de nuevo o escribe tu pregunta.") from error
    finally:
        if uploaded_file is not None and getattr(uploaded_file, "name", None):
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                logger.warning("No se pudo eliminar el archivo temporal de audio de Gemini", exc_info=True)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def synthesize_speech(text: str) -> bytes:
    text = text.strip()
    if not text:
        raise ValueError("No hay texto para reproducir.")
    if len(text) > 2000:
        raise ValueError("El texto supera el límite de síntesis.")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VoiceConfigurationError("La función de voz no está configurada.")

    try:
        from google import genai
    except ImportError as error:
        raise VoiceConfigurationError("Instala las dependencias de voz de Gemini.") from error

    try:
        client = genai.Client(api_key=api_key)
        interaction = client.interactions.create(
            model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts").strip(),
            input=[{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": text,
                    "annotations": [{
                        "type": "speech_metadata",
                        "style": "Habla con voz masculina mexicana, cálida, cercana y de tono bajo, como un guía amable del campus universitario. Mantén un ritmo natural, claro y tranquilo, con energía positiva sin sonar exagerado.",
                    }],
                }],
            }],
            response_format={"type": "audio"},
            generation_config={
                "speech_config": [{"voice": os.getenv("GEMINI_TTS_VOICE", "es-419-concierge-8").strip()}]
            },
            store=False,
            timeout=8,
        )
        audio_data = getattr(getattr(interaction, "output_audio", None), "data", None)
        if not audio_data:
            raise VoiceServiceError("Gemini no generó audio.")
        if isinstance(audio_data, str):
            audio = base64.b64decode(audio_data, validate=True)
        else:
            audio = bytes(audio_data)
        if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
            raise VoiceServiceError("El servicio devolvió un audio no compatible.")
        if len(audio) > MAX_SPEECH_BYTES:
            raise VoiceServiceError("El audio generado supera el tamaño permitido.")
        return audio
    except VoiceServiceError:
        raise
    except Exception as error:
        logger.warning("Gemini no pudo sintetizar la respuesta", exc_info=True)
        raise VoiceServiceError("No se pudo generar la voz. La respuesta escrita sigue disponible.") from error


def synthesize_speech_stream(text: str):
    text = text.strip()
    if not text:
        raise ValueError("No hay texto para reproducir.")
    if len(text) > 2000:
        raise ValueError("El texto supera el límite de síntesis.")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VoiceConfigurationError("La función de voz no está configurada.")

    try:
        from google import genai
    except ImportError as error:
        raise VoiceConfigurationError("Instala las dependencias de voz de Gemini.") from error

    try:
        client = genai.Client(api_key=api_key)
        events = client.interactions.create(
            model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts").strip(),
            input=[{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": text,
                    "annotations": [{
                        "type": "speech_metadata",
                        "style": "Habla con voz masculina mexicana, cálida, cercana y de tono bajo, como un guía amable del campus universitario. Mantén un ritmo natural, claro y tranquilo, con energía positiva sin sonar exagerado.",
                    }],
                }],
            }],
            response_format={"type": "audio", "mime_type": "audio/l16", "sample_rate": 24000},
            generation_config={
                "speech_config": [{"voice": os.getenv("GEMINI_TTS_VOICE", "es-419-concierge-8").strip()}]
            },
            store=False,
            stream=True,
            timeout=8,
        )
        for event in events:
            if event.event_type == "step.delta" and getattr(event.delta, "type", None) == "audio":
                audio_data = getattr(event.delta, "data", None)
                if audio_data:
                    yield base64.b64decode(audio_data, validate=True)
    except (ValueError, VoiceConfigurationError):
        raise
    except Exception as error:
        logger.warning("Gemini no pudo transmitir la respuesta de voz", exc_info=True)
        raise VoiceServiceError("No se pudo transmitir la voz de Gemini.") from error
