"""
Speech State Management.

Provides state tracking for STT/TTS sessions, streaming, and transcription.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .manager import StateManager, StateType

logger = logging.getLogger(__name__)


class AudioSessionStatus(Enum):
    """Status of an audio session."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class StreamingMode(Enum):
    """Streaming mode for audio."""
    NONE = "none"
    REALTIME = "realtime"
    CHUNKED = "chunked"
    CONTINUOUS = "continuous"


class TranscriptionStatus(Enum):
    """Status of transcription."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class AudioChunk:
    """Single audio chunk."""
    chunk_id: str
    sequence: int
    duration_ms: int
    sample_rate: int
    channels: int
    format: str  # wav, mp3, pcm
    size_bytes: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "sequence": self.sequence,
            "duration_ms": self.duration_ms,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "timestamp": self.timestamp,
            "is_final": self.is_final,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioChunk":
        return cls(
            chunk_id=data["chunk_id"],
            sequence=data.get("sequence", 0),
            duration_ms=data.get("duration_ms", 0),
            sample_rate=data.get("sample_rate", 16000),
            channels=data.get("channels", 1),
            format=data.get("format", "wav"),
            size_bytes=data.get("size_bytes", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            is_final=data.get("is_final", False),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TranscriptionResult:
    """Transcription result."""
    text: str
    confidence: float
    is_final: bool
    language: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    speaker_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "is_final": self.is_final,
            "language": self.language,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "words": self.words,
            "alternatives": self.alternatives,
            "speaker_id": self.speaker_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionResult":
        return cls(
            text=data.get("text", ""),
            confidence=data.get("confidence", 0.0),
            is_final=data.get("is_final", False),
            language=data.get("language"),
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", 0.0),
            words=data.get("words", []),
            alternatives=data.get("alternatives", []),
            speaker_id=data.get("speaker_id"),
        )


@dataclass
class STTState:
    """Speech-to-text session state."""
    session_id: str
    status: TranscriptionStatus
    provider: str  # openai, azure, google, local
    model: str
    language: str
    streaming_mode: StreamingMode
    chunks_received: int = 0
    total_duration_ms: int = 0
    transcription: str = ""
    results: List[TranscriptionResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "provider": self.provider,
            "model": self.model,
            "language": self.language,
            "streaming_mode": self.streaming_mode.value,
            "chunks_received": self.chunks_received,
            "total_duration_ms": self.total_duration_ms,
            "transcription": self.transcription,
            "results": [r.to_dict() for r in self.results],
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "STTState":
        return cls(
            session_id=data["session_id"],
            status=TranscriptionStatus(data["status"]),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            language=data.get("language", "en"),
            streaming_mode=StreamingMode(data.get("streaming_mode", "none")),
            chunks_received=data.get("chunks_received", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            transcription=data.get("transcription", ""),
            results=[TranscriptionResult.from_dict(r) for r in data.get("results", [])],
            error=data.get("error"),
            started_at=data.get("started_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TTSState:
    """Text-to-speech session state."""
    session_id: str
    status: AudioSessionStatus
    provider: str  # openai, azure, elevenlabs, local
    model: str
    voice: str
    text: str
    output_format: str = "mp3"
    sample_rate: int = 22050
    streaming: bool = False
    chunks_generated: int = 0
    total_duration_ms: int = 0
    audio_size_bytes: int = 0
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "provider": self.provider,
            "model": self.model,
            "voice": self.voice,
            "text": self.text,
            "output_format": self.output_format,
            "sample_rate": self.sample_rate,
            "streaming": self.streaming,
            "chunks_generated": self.chunks_generated,
            "total_duration_ms": self.total_duration_ms,
            "audio_size_bytes": self.audio_size_bytes,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TTSState":
        return cls(
            session_id=data["session_id"],
            status=AudioSessionStatus(data["status"]),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            voice=data.get("voice", ""),
            text=data.get("text", ""),
            output_format=data.get("output_format", "mp3"),
            sample_rate=data.get("sample_rate", 22050),
            streaming=data.get("streaming", False),
            chunks_generated=data.get("chunks_generated", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            audio_size_bytes=data.get("audio_size_bytes", 0),
            error=data.get("error"),
            started_at=data.get("started_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VoiceConversationState:
    """State for voice conversations (STT + TTS combined)."""
    conversation_id: str
    status: AudioSessionStatus
    current_turn: int = 0
    stt_sessions: List[str] = field(default_factory=list)  # session IDs
    tts_sessions: List[str] = field(default_factory=list)  # session IDs
    transcript: List[Dict[str, str]] = field(default_factory=list)  # role, text
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "status": self.status.value,
            "current_turn": self.current_turn,
            "stt_sessions": self.stt_sessions,
            "tts_sessions": self.tts_sessions,
            "transcript": self.transcript,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "started_at": self.started_at,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceConversationState":
        return cls(
            conversation_id=data["conversation_id"],
            status=AudioSessionStatus(data["status"]),
            current_turn=data.get("current_turn", 0),
            stt_sessions=data.get("stt_sessions", []),
            tts_sessions=data.get("tts_sessions", []),
            transcript=data.get("transcript", []),
            agent_id=data.get("agent_id"),
            user_id=data.get("user_id"),
            started_at=data.get("started_at", datetime.now().isoformat()),
            last_activity=data.get("last_activity", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class SpeechStateManager:
    """
    Manages state for speech sessions (STT and TTS).
    
    Example:
        >>> speech_state = SpeechStateManager()
        >>> 
        >>> # Start STT session
        >>> stt = speech_state.start_stt_session(provider="openai")
        >>> 
        >>> # Add transcription results
        >>> speech_state.add_transcription(stt.session_id, text="Hello", confidence=0.95)
        >>> 
        >>> # Start TTS session
        >>> tts = speech_state.start_tts_session(text="Hi there!", voice="alloy")
        >>> 
        >>> # Voice conversation
        >>> conv = speech_state.start_voice_conversation()
    """
    
    def __init__(self, state_manager: StateManager = None):
        self.state_manager = state_manager or StateManager()
    
    # STT Session Management
    def start_stt_session(
        self,
        provider: str = "openai",
        model: str = "whisper-1",
        language: str = "en",
        streaming_mode: str = "none",
        metadata: Dict = None,
    ) -> STTState:
        """Start a new STT session."""
        import uuid
        session_id = f"stt-{uuid.uuid4().hex[:8]}"
        
        stt = STTState(
            session_id=session_id,
            status=TranscriptionStatus.PENDING,
            provider=provider,
            model=model,
            language=language,
            streaming_mode=StreamingMode(streaming_mode),
            metadata=metadata or {},
        )
        
        self.state_manager.save(
            f"speech_stt:{session_id}",
            stt.to_dict(),
            StateType.SPEECH,
        )
        
        return stt
    
    def get_stt_session(self, session_id: str) -> Optional[STTState]:
        """Get STT session state."""
        data = self.state_manager.get(f"speech_stt:{session_id}")
        if data:
            return STTState.from_dict(data)
        return None
    
    def update_stt_status(
        self,
        session_id: str,
        status: str,
        error: str = None,
    ) -> bool:
        """Update STT session status."""
        stt = self.get_stt_session(session_id)
        if not stt:
            return False
        
        stt.status = TranscriptionStatus(status)
        if error:
            stt.error = error
        if status == "completed":
            stt.completed_at = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_stt:{session_id}",
            stt.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def add_audio_chunk(
        self,
        session_id: str,
        duration_ms: int,
        size_bytes: int = 0,
    ) -> bool:
        """Record received audio chunk."""
        stt = self.get_stt_session(session_id)
        if not stt:
            return False
        
        stt.chunks_received += 1
        stt.total_duration_ms += duration_ms
        
        if stt.status == TranscriptionStatus.PENDING:
            stt.status = TranscriptionStatus.IN_PROGRESS
        
        self.state_manager.save(
            f"speech_stt:{session_id}",
            stt.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def add_transcription(
        self,
        session_id: str,
        text: str,
        confidence: float = 1.0,
        is_final: bool = True,
        language: str = None,
        words: List[Dict] = None,
    ) -> bool:
        """Add transcription result."""
        stt = self.get_stt_session(session_id)
        if not stt:
            return False
        
        result = TranscriptionResult(
            text=text,
            confidence=confidence,
            is_final=is_final,
            language=language or stt.language,
            words=words or [],
        )
        
        stt.results.append(result)
        
        if is_final:
            # Append to full transcription
            if stt.transcription:
                stt.transcription += " " + text
            else:
                stt.transcription = text
        
        self.state_manager.save(
            f"speech_stt:{session_id}",
            stt.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def complete_stt_session(self, session_id: str) -> Optional[str]:
        """Complete STT session and return full transcription."""
        stt = self.get_stt_session(session_id)
        if not stt:
            return None
        
        stt.status = TranscriptionStatus.COMPLETED
        stt.completed_at = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_stt:{session_id}",
            stt.to_dict(),
            StateType.SPEECH,
        )
        
        return stt.transcription
    
    # TTS Session Management
    def start_tts_session(
        self,
        text: str,
        provider: str = "openai",
        model: str = "tts-1",
        voice: str = "alloy",
        output_format: str = "mp3",
        streaming: bool = False,
        metadata: Dict = None,
    ) -> TTSState:
        """Start a new TTS session."""
        import uuid
        session_id = f"tts-{uuid.uuid4().hex[:8]}"
        
        tts = TTSState(
            session_id=session_id,
            status=AudioSessionStatus.PROCESSING,
            provider=provider,
            model=model,
            voice=voice,
            text=text,
            output_format=output_format,
            streaming=streaming,
            metadata=metadata or {},
        )
        
        self.state_manager.save(
            f"speech_tts:{session_id}",
            tts.to_dict(),
            StateType.SPEECH,
        )
        
        return tts
    
    def get_tts_session(self, session_id: str) -> Optional[TTSState]:
        """Get TTS session state."""
        data = self.state_manager.get(f"speech_tts:{session_id}")
        if data:
            return TTSState.from_dict(data)
        return None
    
    def update_tts_progress(
        self,
        session_id: str,
        chunks_generated: int = None,
        duration_ms: int = None,
        audio_size_bytes: int = None,
    ) -> bool:
        """Update TTS generation progress."""
        tts = self.get_tts_session(session_id)
        if not tts:
            return False
        
        if chunks_generated is not None:
            tts.chunks_generated = chunks_generated
        if duration_ms is not None:
            tts.total_duration_ms = duration_ms
        if audio_size_bytes is not None:
            tts.audio_size_bytes = audio_size_bytes
        
        self.state_manager.save(
            f"speech_tts:{session_id}",
            tts.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def start_speaking(self, session_id: str) -> bool:
        """Mark TTS as speaking (playback started)."""
        tts = self.get_tts_session(session_id)
        if not tts:
            return False
        
        tts.status = AudioSessionStatus.SPEAKING
        
        self.state_manager.save(
            f"speech_tts:{session_id}",
            tts.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def complete_tts_session(
        self,
        session_id: str,
        duration_ms: int = None,
        audio_size_bytes: int = None,
    ) -> bool:
        """Complete TTS session."""
        tts = self.get_tts_session(session_id)
        if not tts:
            return False
        
        tts.status = AudioSessionStatus.COMPLETED
        tts.completed_at = datetime.now().isoformat()
        if duration_ms is not None:
            tts.total_duration_ms = duration_ms
        if audio_size_bytes is not None:
            tts.audio_size_bytes = audio_size_bytes
        
        self.state_manager.save(
            f"speech_tts:{session_id}",
            tts.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def fail_tts_session(self, session_id: str, error: str) -> bool:
        """Mark TTS session as failed."""
        tts = self.get_tts_session(session_id)
        if not tts:
            return False
        
        tts.status = AudioSessionStatus.ERROR
        tts.error = error
        tts.completed_at = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_tts:{session_id}",
            tts.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    # Voice Conversation Management
    def start_voice_conversation(
        self,
        agent_id: str = None,
        user_id: str = None,
        metadata: Dict = None,
    ) -> VoiceConversationState:
        """Start a new voice conversation."""
        import uuid
        conversation_id = f"voice-{uuid.uuid4().hex[:8]}"
        
        conv = VoiceConversationState(
            conversation_id=conversation_id,
            status=AudioSessionStatus.IDLE,
            agent_id=agent_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        
        self.state_manager.save(
            f"speech_conv:{conversation_id}",
            conv.to_dict(),
            StateType.SPEECH,
        )
        
        return conv
    
    def get_voice_conversation(
        self,
        conversation_id: str,
    ) -> Optional[VoiceConversationState]:
        """Get voice conversation state."""
        data = self.state_manager.get(f"speech_conv:{conversation_id}")
        if data:
            return VoiceConversationState.from_dict(data)
        return None
    
    def add_user_turn(
        self,
        conversation_id: str,
        text: str,
        stt_session_id: str = None,
    ) -> bool:
        """Add user turn to conversation."""
        conv = self.get_voice_conversation(conversation_id)
        if not conv:
            return False
        
        conv.current_turn += 1
        conv.transcript.append({"role": "user", "text": text})
        if stt_session_id:
            conv.stt_sessions.append(stt_session_id)
        conv.last_activity = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_conv:{conversation_id}",
            conv.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def add_agent_turn(
        self,
        conversation_id: str,
        text: str,
        tts_session_id: str = None,
    ) -> bool:
        """Add agent turn to conversation."""
        conv = self.get_voice_conversation(conversation_id)
        if not conv:
            return False
        
        conv.current_turn += 1
        conv.transcript.append({"role": "agent", "text": text})
        if tts_session_id:
            conv.tts_sessions.append(tts_session_id)
        conv.last_activity = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_conv:{conversation_id}",
            conv.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def update_conversation_status(
        self,
        conversation_id: str,
        status: str,
    ) -> bool:
        """Update conversation status."""
        conv = self.get_voice_conversation(conversation_id)
        if not conv:
            return False
        
        conv.status = AudioSessionStatus(status)
        conv.last_activity = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_conv:{conversation_id}",
            conv.to_dict(),
            StateType.SPEECH,
        )
        return True
    
    def end_voice_conversation(
        self,
        conversation_id: str,
    ) -> Optional[List[Dict[str, str]]]:
        """End conversation and return transcript."""
        conv = self.get_voice_conversation(conversation_id)
        if not conv:
            return None
        
        conv.status = AudioSessionStatus.COMPLETED
        conv.last_activity = datetime.now().isoformat()
        
        self.state_manager.save(
            f"speech_conv:{conversation_id}",
            conv.to_dict(),
            StateType.SPEECH,
        )
        
        return conv.transcript
    
    # Utility Methods
    def get_active_sessions(self) -> Dict[str, List[str]]:
        """Get all active speech sessions."""
        stt_keys = self.state_manager.list("speech_stt:")
        tts_keys = self.state_manager.list("speech_tts:")
        conv_keys = self.state_manager.list("speech_conv:")
        
        active = {"stt": [], "tts": [], "conversations": []}
        
        for key in stt_keys:
            data = self.state_manager.get(key)
            if data:
                stt = STTState.from_dict(data)
                if stt.status == TranscriptionStatus.IN_PROGRESS:
                    active["stt"].append(stt.session_id)
        
        for key in tts_keys:
            data = self.state_manager.get(key)
            if data:
                tts = TTSState.from_dict(data)
                if tts.status in [AudioSessionStatus.PROCESSING, AudioSessionStatus.SPEAKING]:
                    active["tts"].append(tts.session_id)
        
        for key in conv_keys:
            data = self.state_manager.get(key)
            if data:
                conv = VoiceConversationState.from_dict(data)
                if conv.status not in [AudioSessionStatus.COMPLETED, AudioSessionStatus.ERROR]:
                    active["conversations"].append(conv.conversation_id)
        
        return active
    
    def cleanup_completed_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old completed sessions."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        count = 0
        
        # Clean STT sessions
        for key in self.state_manager.list("speech_stt:"):
            data = self.state_manager.get(key)
            if data:
                stt = STTState.from_dict(data)
                if stt.completed_at and datetime.fromisoformat(stt.completed_at) < cutoff:
                    if self.state_manager.delete(key):
                        count += 1
        
        # Clean TTS sessions
        for key in self.state_manager.list("speech_tts:"):
            data = self.state_manager.get(key)
            if data:
                tts = TTSState.from_dict(data)
                if tts.completed_at and datetime.fromisoformat(tts.completed_at) < cutoff:
                    if self.state_manager.delete(key):
                        count += 1
        
        return count


__all__ = [
    "AudioSessionStatus",
    "StreamingMode",
    "TranscriptionStatus",
    "AudioChunk",
    "TranscriptionResult",
    "STTState",
    "TTSState",
    "VoiceConversationState",
    "SpeechStateManager",
]
