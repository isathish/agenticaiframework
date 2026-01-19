"""
Speech Processing Implementation.

STT (Speech-to-Text) and TTS (Text-to-Speech) providers
for voice-enabled agent interactions.
"""

import base64
import io
import json
import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO, Generator

logger = logging.getLogger(__name__)


class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"
    WEBM = "webm"
    M4A = "m4a"
    PCM = "pcm"


@dataclass
class VoiceConfig:
    """Voice configuration for TTS."""
    voice_id: str = "alloy"
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    style: Optional[str] = None  # e.g., "cheerful", "professional"
    
    # Provider-specific settings
    model: Optional[str] = None
    custom_voice_id: Optional[str] = None


@dataclass
class STTResult:
    """Speech-to-Text result."""
    text: str
    confidence: float = 1.0
    language: str = "en"
    duration_seconds: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    provider: str = ""
    processing_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "duration_seconds": self.duration_seconds,
            "words": self.words,
            "alternatives": self.alternatives,
            "provider": self.provider,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class TTSResult:
    """Text-to-Speech result."""
    audio_data: bytes
    format: AudioFormat = AudioFormat.MP3
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    provider: str = ""
    processing_time_ms: int = 0
    
    def save(self, path: str) -> None:
        """Save audio to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.audio_data)
    
    def to_base64(self) -> str:
        """Encode audio as base64."""
        return base64.b64encode(self.audio_data).decode()
    
    def to_data_uri(self) -> str:
        """Get data URI for embedding."""
        mime_types = {
            AudioFormat.MP3: "audio/mpeg",
            AudioFormat.WAV: "audio/wav",
            AudioFormat.OGG: "audio/ogg",
            AudioFormat.FLAC: "audio/flac",
        }
        mime = mime_types.get(self.format, "audio/mpeg")
        return f"data:{mime};base64,{self.to_base64()}"
    
    def get_bytes_io(self) -> io.BytesIO:
        """Get BytesIO object for streaming."""
        return io.BytesIO(self.audio_data)


class STTProvider(ABC):
    """Abstract base class for STT providers."""
    
    @abstractmethod
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe audio to text."""
        pass
    
    @abstractmethod
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription (for real-time)."""
        pass


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize text to speech."""
        pass
    
    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream audio synthesis."""
        pass
    
    @abstractmethod
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available voices."""
        pass


class OpenAISTT(STTProvider):
    """
    OpenAI Whisper STT provider.
    
    Example:
        >>> stt = OpenAISTT(api_key="...")
        >>> result = stt.transcribe("speech.mp3")
        >>> print(result.text)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
    
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe audio using OpenAI Whisper."""
        try:
            import httpx
        except ImportError:
            raise ImportError("OpenAI STT requires: pip install httpx")
        
        start_time = time.time()
        
        # Prepare audio file
        if isinstance(audio, str):
            with open(audio, "rb") as f:
                audio_data = f.read()
            filename = Path(audio).name
        elif isinstance(audio, bytes):
            audio_data = audio
            filename = "audio.mp3"
        else:
            audio_data = audio.read()
            filename = getattr(audio, "name", "audio.mp3")
        
        # Make request
        files = {"file": (filename, audio_data)}
        data = {"model": self.model}
        
        if language:
            data["language"] = language
        
        if kwargs.get("response_format"):
            data["response_format"] = kwargs["response_format"]
        
        if kwargs.get("prompt"):
            data["prompt"] = kwargs["prompt"]
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
        
        result = response.json()
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Handle different response formats
        if isinstance(result, str):
            text = result
            words = []
        elif "text" in result:
            text = result["text"]
            words = result.get("words", [])
        else:
            text = str(result)
            words = []
        
        return STTResult(
            text=text,
            confidence=1.0,
            language=language or "en",
            words=words,
            provider="openai",
            processing_time_ms=processing_time,
        )
    
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription (collect audio then transcribe)."""
        # Collect audio chunks
        audio_chunks = []
        for chunk in audio_stream:
            audio_chunks.append(chunk)
        
        # Transcribe complete audio
        audio_data = b"".join(audio_chunks)
        result = self.transcribe(audio_data, **kwargs)
        yield result.text


class OpenAITTS(TTSProvider):
    """
    OpenAI TTS provider.
    
    Example:
        >>> tts = OpenAITTS(api_key="...")
        >>> result = tts.synthesize("Hello, world!")
        >>> result.save("hello.mp3")
    """
    
    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    MODELS = ["tts-1", "tts-1-hd"]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "tts-1",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
    
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech from text."""
        try:
            import httpx
        except ImportError:
            raise ImportError("OpenAI TTS requires: pip install httpx")
        
        start_time = time.time()
        
        voice = voice or VoiceConfig()
        voice_id = voice.voice_id if voice.voice_id in self.VOICES else "alloy"
        
        data = {
            "model": voice.model or self.model,
            "input": text,
            "voice": voice_id,
            "speed": voice.speed,
            "response_format": kwargs.get("format", "mp3"),
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/audio/speech",
                headers=headers,
                json=data,
            )
            response.raise_for_status()
        
        audio_data = response.content
        processing_time = int((time.time() - start_time) * 1000)
        
        format_map = {
            "mp3": AudioFormat.MP3,
            "opus": AudioFormat.OGG,
            "aac": AudioFormat.M4A,
            "flac": AudioFormat.FLAC,
        }
        
        return TTSResult(
            audio_data=audio_data,
            format=format_map.get(kwargs.get("format", "mp3"), AudioFormat.MP3),
            provider="openai",
            processing_time_ms=processing_time,
        )
    
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream audio synthesis."""
        try:
            import httpx
        except ImportError:
            raise ImportError("OpenAI TTS requires: pip install httpx")
        
        voice = voice or VoiceConfig()
        voice_id = voice.voice_id if voice.voice_id in self.VOICES else "alloy"
        
        data = {
            "model": voice.model or self.model,
            "input": text,
            "voice": voice_id,
            "speed": voice.speed,
            "response_format": kwargs.get("format", "mp3"),
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/audio/speech",
                headers=headers,
                json=data,
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    yield chunk
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available voices."""
        return [
            {"id": "alloy", "name": "Alloy", "gender": "neutral"},
            {"id": "echo", "name": "Echo", "gender": "male"},
            {"id": "fable", "name": "Fable", "gender": "female"},
            {"id": "onyx", "name": "Onyx", "gender": "male"},
            {"id": "nova", "name": "Nova", "gender": "female"},
            {"id": "shimmer", "name": "Shimmer", "gender": "female"},
        ]


class AzureSTT(STTProvider):
    """
    Azure Cognitive Services STT provider.
    
    Example:
        >>> stt = AzureSTT(
        ...     api_key="...",
        ...     region="eastus"
        ... )
        >>> result = stt.transcribe("speech.wav")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        region: str = "eastus",
        language: str = "en-US",
    ):
        self.api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = region
        self.language = language
        self.endpoint = f"https://{region}.stt.speech.microsoft.com"
    
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe audio using Azure Speech Services."""
        try:
            import httpx
        except ImportError:
            raise ImportError("Azure STT requires: pip install httpx")
        
        start_time = time.time()
        
        # Prepare audio
        if isinstance(audio, str):
            with open(audio, "rb") as f:
                audio_data = f.read()
        elif isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()
        
        lang = language or self.language
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "audio/wav",
            "Accept": "application/json",
        }
        
        url = (
            f"{self.endpoint}/speech/recognition/conversation/cognitiveservices/v1"
            f"?language={lang}"
        )
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, content=audio_data)
            response.raise_for_status()
        
        result = response.json()
        processing_time = int((time.time() - start_time) * 1000)
        
        return STTResult(
            text=result.get("DisplayText", ""),
            confidence=result.get("RecognitionStatus") == "Success",
            language=lang,
            duration_seconds=result.get("Duration", 0) / 10000000,
            provider="azure",
            processing_time_ms=processing_time,
        )
    
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription."""
        # Azure supports WebSocket streaming - simplified here
        audio_chunks = []
        for chunk in audio_stream:
            audio_chunks.append(chunk)
        
        audio_data = b"".join(audio_chunks)
        result = self.transcribe(audio_data, **kwargs)
        yield result.text


class AzureTTS(TTSProvider):
    """
    Azure Cognitive Services TTS provider.
    
    Example:
        >>> tts = AzureTTS(
        ...     api_key="...",
        ...     region="eastus"
        ... )
        >>> result = tts.synthesize("Hello!")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        region: str = "eastus",
        voice: str = "en-US-JennyNeural",
    ):
        self.api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = region
        self.default_voice = voice
        self.endpoint = f"https://{region}.tts.speech.microsoft.com"
    
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech using Azure."""
        try:
            import httpx
        except ImportError:
            raise ImportError("Azure TTS requires: pip install httpx")
        
        start_time = time.time()
        
        voice_config = voice or VoiceConfig()
        voice_name = voice_config.voice_id or self.default_voice
        
        # Build SSML
        ssml = f"""
        <speak version='1.0' xml:lang='en-US'>
            <voice name='{voice_name}'>
                <prosody rate='{voice_config.speed}' pitch='{int((voice_config.pitch - 1) * 100)}%'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        }
        
        url = f"{self.endpoint}/cognitiveservices/v1"
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, content=ssml)
            response.raise_for_status()
        
        audio_data = response.content
        processing_time = int((time.time() - start_time) * 1000)
        
        return TTSResult(
            audio_data=audio_data,
            format=AudioFormat.MP3,
            sample_rate=16000,
            provider="azure",
            processing_time_ms=processing_time,
        )
    
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream synthesis."""
        result = self.synthesize(text, voice, **kwargs)
        # Return in chunks
        chunk_size = 4096
        for i in range(0, len(result.audio_data), chunk_size):
            yield result.audio_data[i:i + chunk_size]
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available Azure voices."""
        try:
            import httpx
        except ImportError:
            return []
        
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        url = f"{self.endpoint}/cognitiveservices/voices/list"
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list Azure voices: {e}")
            return []


class GoogleSTT(STTProvider):
    """
    Google Cloud Speech-to-Text provider.
    
    Example:
        >>> stt = GoogleSTT(credentials_path="service-account.json")
        >>> result = stt.transcribe("speech.wav")
    """
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        language: str = "en-US",
    ):
        self.credentials_path = credentials_path
        self.language = language
        
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe using Google Cloud Speech."""
        try:
            from google.cloud import speech
        except ImportError:
            raise ImportError("Google STT requires: pip install google-cloud-speech")
        
        start_time = time.time()
        
        # Prepare audio
        if isinstance(audio, str):
            with open(audio, "rb") as f:
                audio_data = f.read()
        elif isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()
        
        client = speech.SpeechClient()
        
        audio_obj = speech.RecognitionAudio(content=audio_data)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language or self.language,
            enable_word_time_offsets=True,
        )
        
        response = client.recognize(config=config, audio=audio_obj)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Process results
        text = ""
        words = []
        confidence = 0.0
        
        for result in response.results:
            alt = result.alternatives[0]
            text += alt.transcript + " "
            confidence = alt.confidence
            
            for word_info in alt.words:
                words.append({
                    "word": word_info.word,
                    "start_time": word_info.start_time.total_seconds(),
                    "end_time": word_info.end_time.total_seconds(),
                })
        
        return STTResult(
            text=text.strip(),
            confidence=confidence,
            language=language or self.language,
            words=words,
            provider="google",
            processing_time_ms=processing_time,
        )
    
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription."""
        try:
            from google.cloud import speech
        except ImportError:
            raise ImportError("Google STT requires: pip install google-cloud-speech")
        
        client = speech.SpeechClient()
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=kwargs.get("language", self.language),
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )
        
        def request_generator():
            yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
            for chunk in audio_stream:
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
        
        responses = client.streaming_recognize(requests=request_generator())
        
        for response in responses:
            for result in response.results:
                if result.is_final:
                    yield result.alternatives[0].transcript


class GoogleTTS(TTSProvider):
    """
    Google Cloud Text-to-Speech provider.
    """
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        language: str = "en-US",
        voice: str = "en-US-Standard-A",
    ):
        self.credentials_path = credentials_path
        self.language = language
        self.default_voice = voice
        
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize using Google Cloud TTS."""
        try:
            from google.cloud import texttospeech
        except ImportError:
            raise ImportError("Google TTS requires: pip install google-cloud-texttospeech")
        
        start_time = time.time()
        
        client = texttospeech.TextToSpeechClient()
        
        voice_config = voice or VoiceConfig()
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=voice_config.language,
            name=voice_config.voice_id or self.default_voice,
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=voice_config.speed,
            pitch=voice_config.pitch,
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return TTSResult(
            audio_data=response.audio_content,
            format=AudioFormat.MP3,
            provider="google",
            processing_time_ms=processing_time,
        )
    
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream synthesis."""
        result = self.synthesize(text, voice, **kwargs)
        chunk_size = 4096
        for i in range(0, len(result.audio_data), chunk_size):
            yield result.audio_data[i:i + chunk_size]
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available Google voices."""
        try:
            from google.cloud import texttospeech
        except ImportError:
            return []
        
        client = texttospeech.TextToSpeechClient()
        response = client.list_voices()
        
        voices = []
        for voice in response.voices:
            voices.append({
                "id": voice.name,
                "language_codes": list(voice.language_codes),
                "gender": voice.ssml_gender.name,
            })
        
        return voices


class ElevenLabsTTS(TTSProvider):
    """
    ElevenLabs TTS provider for high-quality voice synthesis.
    
    Example:
        >>> tts = ElevenLabsTTS(api_key="...")
        >>> result = tts.synthesize("Hello!", voice=VoiceConfig(voice_id="rachel"))
        >>> result.save("hello.mp3")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "eleven_monolingual_v1",
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.model = model
        self.base_url = "https://api.elevenlabs.io/v1"
    
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech using ElevenLabs."""
        try:
            import httpx
        except ImportError:
            raise ImportError("ElevenLabs TTS requires: pip install httpx")
        
        start_time = time.time()
        
        voice_config = voice or VoiceConfig()
        voice_id = voice_config.voice_id or "21m00Tcm4TlvDq8ikWAM"  # Rachel
        
        data = {
            "text": text,
            "model_id": voice_config.model or self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
        
        audio_data = response.content
        processing_time = int((time.time() - start_time) * 1000)
        
        return TTSResult(
            audio_data=audio_data,
            format=AudioFormat.MP3,
            provider="elevenlabs",
            processing_time_ms=processing_time,
        )
    
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream audio synthesis."""
        try:
            import httpx
        except ImportError:
            raise ImportError("ElevenLabs TTS requires: pip install httpx")
        
        voice_config = voice or VoiceConfig()
        voice_id = voice_config.voice_id or "21m00Tcm4TlvDq8ikWAM"
        
        data = {
            "text": text,
            "model_id": voice_config.model or self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
        
        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", url, headers=headers, json=data) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    yield chunk
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available ElevenLabs voices."""
        try:
            import httpx
        except ImportError:
            return []
        
        headers = {"xi-api-key": self.api_key}
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{self.base_url}/voices", headers=headers)
                response.raise_for_status()
            
            data = response.json()
            return [
                {
                    "id": v["voice_id"],
                    "name": v["name"],
                    "category": v.get("category", ""),
                    "labels": v.get("labels", {}),
                }
                for v in data.get("voices", [])
            ]
        except Exception as e:
            logger.error(f"Failed to list ElevenLabs voices: {e}")
            return []


class WhisperLocalSTT(STTProvider):
    """
    Local Whisper STT using OpenAI's Whisper model.
    
    Example:
        >>> stt = WhisperLocalSTT(model_size="base")
        >>> result = stt.transcribe("speech.mp3")
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
    ):
        self.model_size = model_size
        self.device = device
        self._model = None
    
    def _load_model(self):
        """Lazy load Whisper model."""
        if self._model is None:
            try:
                import whisper
            except ImportError:
                raise ImportError("Local Whisper requires: pip install openai-whisper")
            
            self._model = whisper.load_model(self.model_size, device=self.device)
        
        return self._model
    
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe using local Whisper."""
        model = self._load_model()
        
        start_time = time.time()
        
        # Handle different input types
        if isinstance(audio, str):
            audio_path = audio
        else:
            # Save to temp file
            if isinstance(audio, bytes):
                audio_data = audio
            else:
                audio_data = audio.read()
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                audio_path = f.name
        
        try:
            result = model.transcribe(
                audio_path,
                language=language,
                **kwargs,
            )
        finally:
            # Clean up temp file
            if not isinstance(audio, str):
                os.unlink(audio_path)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Extract word-level timestamps if available
        words = []
        if "segments" in result:
            for segment in result["segments"]:
                if "words" in segment:
                    words.extend(segment["words"])
        
        return STTResult(
            text=result["text"],
            confidence=1.0,
            language=result.get("language", language or "en"),
            words=words,
            provider="whisper_local",
            processing_time_ms=processing_time,
        )
    
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription (collect then transcribe)."""
        audio_chunks = []
        for chunk in audio_stream:
            audio_chunks.append(chunk)
        
        audio_data = b"".join(audio_chunks)
        result = self.transcribe(audio_data, **kwargs)
        yield result.text


class SpeechProcessor:
    """
    Main speech processor combining STT and TTS.
    
    Example:
        >>> speech = SpeechProcessor(
        ...     stt_provider="openai",
        ...     tts_provider="elevenlabs",
        ...     openai_api_key="...",
        ...     elevenlabs_api_key="..."
        ... )
        >>> 
        >>> # Transcribe audio
        >>> result = speech.transcribe("question.mp3")
        >>> print(result.text)
        >>> 
        >>> # Generate response audio
        >>> response = speech.synthesize("Here's my answer...")
        >>> response.save("answer.mp3")
        >>> 
        >>> # Full voice conversation
        >>> user_text = speech.listen("user_audio.mp3")
        >>> agent_response = process_with_agent(user_text)
        >>> speech.speak(agent_response, save_to="response.mp3")
    """
    
    STT_PROVIDERS = {
        "openai": OpenAISTT,
        "azure": AzureSTT,
        "google": GoogleSTT,
        "whisper_local": WhisperLocalSTT,
    }
    
    TTS_PROVIDERS = {
        "openai": OpenAITTS,
        "azure": AzureTTS,
        "google": GoogleTTS,
        "elevenlabs": ElevenLabsTTS,
    }
    
    def __init__(
        self,
        stt_provider: str = "openai",
        tts_provider: str = "openai",
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ):
        self.voice = voice or VoiceConfig()
        
        # Initialize STT provider
        stt_class = self.STT_PROVIDERS.get(stt_provider)
        if stt_class:
            stt_kwargs = {k: v for k, v in kwargs.items() 
                         if k.startswith("stt_") or k in ["api_key", "openai_api_key"]}
            # Clean prefixes
            stt_kwargs = {k.replace("stt_", "").replace("openai_", ""): v 
                         for k, v in stt_kwargs.items()}
            self._stt = stt_class(**stt_kwargs)
        else:
            self._stt = None
        
        # Initialize TTS provider
        tts_class = self.TTS_PROVIDERS.get(tts_provider)
        if tts_class:
            tts_kwargs = {k: v for k, v in kwargs.items() 
                         if k.startswith("tts_") or k.startswith(f"{tts_provider}_") 
                         or k in ["api_key", "openai_api_key"]}
            # Clean prefixes
            tts_kwargs = {k.replace("tts_", "").replace(f"{tts_provider}_", "").replace("openai_", ""): v 
                         for k, v in tts_kwargs.items()}
            self._tts = tts_class(**tts_kwargs)
        else:
            self._tts = None
    
    def transcribe(
        self,
        audio: Union[str, bytes, BinaryIO],
        language: Optional[str] = None,
        **kwargs,
    ) -> STTResult:
        """Transcribe audio to text."""
        if not self._stt:
            raise ValueError("No STT provider configured")
        return self._stt.transcribe(audio, language, **kwargs)
    
    def synthesize(
        self,
        text: str,
        voice: Optional[VoiceConfig] = None,
        **kwargs,
    ) -> TTSResult:
        """Synthesize text to speech."""
        if not self._tts:
            raise ValueError("No TTS provider configured")
        return self._tts.synthesize(text, voice or self.voice, **kwargs)
    
    def listen(
        self,
        audio: Union[str, bytes, BinaryIO],
        **kwargs,
    ) -> str:
        """Listen to audio and return text (convenience method)."""
        result = self.transcribe(audio, **kwargs)
        return result.text
    
    def speak(
        self,
        text: str,
        save_to: Optional[str] = None,
        **kwargs,
    ) -> TTSResult:
        """Convert text to speech and optionally save."""
        result = self.synthesize(text, **kwargs)
        if save_to:
            result.save(save_to)
        return result
    
    def transcribe_stream(
        self,
        audio_stream: Generator[bytes, None, None],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream transcription."""
        if not self._stt:
            raise ValueError("No STT provider configured")
        return self._stt.transcribe_stream(audio_stream, **kwargs)
    
    def synthesize_stream(
        self,
        text: str,
        **kwargs,
    ) -> Generator[bytes, None, None]:
        """Stream synthesis."""
        if not self._tts:
            raise ValueError("No TTS provider configured")
        return self._tts.synthesize_stream(text, self.voice, **kwargs)
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available TTS voices."""
        if not self._tts:
            return []
        return self._tts.list_voices()
    
    def set_voice(self, voice: VoiceConfig) -> None:
        """Set default voice configuration."""
        self.voice = voice


__all__ = [
    # Types
    "AudioFormat",
    "STTResult",
    "TTSResult",
    "VoiceConfig",
    # Providers
    "STTProvider",
    "TTSProvider",
    "OpenAISTT",
    "OpenAITTS",
    "AzureSTT",
    "AzureTTS",
    "GoogleSTT",
    "GoogleTTS",
    "ElevenLabsTTS",
    "WhisperLocalSTT",
    # Main class
    "SpeechProcessor",
]
