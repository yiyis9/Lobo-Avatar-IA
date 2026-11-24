import base64
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.gemini_voice import synthesize_speech, transcribe_wav


def sample_wav() -> bytes:
    return b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 36


class GeminiVoiceTests(unittest.TestCase):
    def test_transcription_uploads_and_deletes_temporary_audio(self) -> None:
        import google.genai

        client = MagicMock()
        client.files.upload.return_value = SimpleNamespace(uri="https://files.example/audio", name="files/audio")
        client.interactions.create.return_value = SimpleNamespace(output_text="¿Dónde está Servicios Escolares?")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch.object(google.genai, "Client", return_value=client):
                transcript = transcribe_wav(sample_wav())

        self.assertEqual(transcript, "¿Dónde está Servicios Escolares?")
        call = client.interactions.create.call_args.kwargs
        self.assertEqual(call["model"], "gemini-3.5-transcribe")
        self.assertFalse(call["store"])
        self.assertEqual(call["generation_config"]["transcription_config"]["language_codes"], ["es-MX"])
        client.files.delete.assert_called_once_with(name="files/audio")
        uploaded_path = Path(client.files.upload.call_args.kwargs["file"])
        self.assertFalse(uploaded_path.exists())

    def test_synthesis_returns_wav_audio_without_persisting_interaction(self) -> None:
        import google.genai

        wav = sample_wav()
        client = MagicMock()
        client.interactions.create.return_value = SimpleNamespace(
            output_audio=SimpleNamespace(data=base64.b64encode(wav).decode("ascii"))
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch.object(google.genai, "Client", return_value=client):
                result = synthesize_speech("Bienvenida a la UPVT.")

        self.assertEqual(result, wav)
        call = client.interactions.create.call_args.kwargs
        self.assertEqual(call["model"], "gemini-3.8-flash-tts")
        self.assertFalse(call["store"])
        self.assertEqual(call["timeout"], 8)
        self.assertEqual(call["response_format"], {"type": "audio"})
        self.assertEqual(call["generation_config"]["speech_config"], [{"voice": "es-419-concierge-8"}])
        style = call["input"][0]["content"][0]["annotations"][0]["style"]
        self.assertIn("cálida", style)
        self.assertIn("voz masculina mexicana", style)
        self.assertIn("voz masculina", style)

    def test_transcription_rejects_non_wav_input(self) -> None:
        with self.assertRaises(ValueError):
            transcribe_wav(b"not wav")


if __name__ == "__main__":
    unittest.main()
