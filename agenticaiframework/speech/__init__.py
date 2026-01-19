"""
Speech Module - Speech-to-Text (STT) and Text-to-Speech (TTS).

Provides voice input/output capabilities for agents with
multiple provider support.

Providers:
- OpenAI (Whisper for STT, TTS-1 for TTS)
- Azure Cognitive Services
- Google Cloud Speech
- ElevenLabs (TTS)
- Local models (Whisper local, Coqui TTS)

Example:
    >>> from agenticaiframework.speech import SpeechProcessor, STTProvider, TTSProvider
    >>> 
    >>> # Create speech processor
    >>> speech = SpeechProcessor(
    ...     stt_provider="openai",
    ...     tts_provider="elevenlabs"
    ... )
    >>> 
    >>> # Speech to text
    >>> text = speech.transcribe("audio.mp3")
    >>> 
    >>> # Text to speech
    >>> audio = speech.synthesize("Hello, how can I help?")
    >>> audio.save("response.mp3")
"""

from .processor import (
    # Types
    AudioFormat,
    STTResult,
    TTSResult,
    VoiceConfig,
    # Providers
    STTProvider,
    TTSProvider,
    OpenAISTT,
    OpenAITTS,
    AzureSTT,
    AzureTTS,
    GoogleSTT,
    GoogleTTS,
    ElevenLabsTTS,
    WhisperLocalSTT,
    # Main class
    SpeechProcessor,
)

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
