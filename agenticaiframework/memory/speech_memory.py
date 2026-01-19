"""
Speech Memory Management.

Provides memory for speech operations:
- Transcription history
- Voice profiles
- Audio session cache
- Conversation transcripts
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .manager import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionMemory:
    """Memory of a transcription."""
    transcription_id: str
    audio_hash: str
    text: str
    language: str
    confidence: float
    provider: str
    model: str
    duration_ms: int
    word_count: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    words: List[Dict[str, Any]] = field(default_factory=list)
    speaker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcription_id": self.transcription_id,
            "audio_hash": self.audio_hash,
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "provider": self.provider,
            "model": self.model,
            "duration_ms": self.duration_ms,
            "word_count": self.word_count,
            "timestamp": self.timestamp,
            "words": self.words,
            "speaker_id": self.speaker_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionMemory":
        return cls(
            transcription_id=data["transcription_id"],
            audio_hash=data["audio_hash"],
            text=data["text"],
            language=data.get("language", "en"),
            confidence=data.get("confidence", 1.0),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            duration_ms=data.get("duration_ms", 0),
            word_count=data.get("word_count", len(data.get("text", "").split())),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            words=data.get("words", []),
            speaker_id=data.get("speaker_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SynthesisMemory:
    """Memory of a TTS synthesis."""
    synthesis_id: str
    text_hash: str
    text: str
    voice: str
    provider: str
    model: str
    audio_format: str
    duration_ms: int
    audio_size_bytes: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "text_hash": self.text_hash,
            "text": self.text,
            "voice": self.voice,
            "provider": self.provider,
            "model": self.model,
            "audio_format": self.audio_format,
            "duration_ms": self.duration_ms,
            "audio_size_bytes": self.audio_size_bytes,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynthesisMemory":
        return cls(
            synthesis_id=data["synthesis_id"],
            text_hash=data["text_hash"],
            text=data["text"],
            voice=data.get("voice", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            audio_format=data.get("audio_format", "mp3"),
            duration_ms=data.get("duration_ms", 0),
            audio_size_bytes=data.get("audio_size_bytes", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VoiceProfile:
    """Profile for a voice/speaker."""
    profile_id: str
    name: str
    profile_type: str  # user, agent, system
    preferred_language: str = "en"
    speaking_rate: float = 1.0
    pitch: float = 1.0
    voice_settings: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None  # Voice embedding for speaker ID
    sample_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "profile_type": self.profile_type,
            "preferred_language": self.preferred_language,
            "speaking_rate": self.speaking_rate,
            "pitch": self.pitch,
            "voice_settings": self.voice_settings,
            "embedding": self.embedding,
            "sample_count": self.sample_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceProfile":
        return cls(
            profile_id=data["profile_id"],
            name=data["name"],
            profile_type=data.get("profile_type", "user"),
            preferred_language=data.get("preferred_language", "en"),
            speaking_rate=data.get("speaking_rate", 1.0),
            pitch=data.get("pitch", 1.0),
            voice_settings=data.get("voice_settings", {}),
            embedding=data.get("embedding"),
            sample_count=data.get("sample_count", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class VoiceConversationMemory:
    """Memory of a voice conversation."""
    conversation_id: str
    participants: List[str]  # profile_ids
    turns: List[Dict[str, Any]]  # role, text, audio_id, timestamp
    total_duration_ms: int = 0
    turn_count: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None
    summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "participants": self.participants,
            "turns": self.turns,
            "total_duration_ms": self.total_duration_ms,
            "turn_count": self.turn_count,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": self.summary,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceConversationMemory":
        return cls(
            conversation_id=data["conversation_id"],
            participants=data.get("participants", []),
            turns=data.get("turns", []),
            total_duration_ms=data.get("total_duration_ms", 0),
            turn_count=data.get("turn_count", 0),
            started_at=data.get("started_at", datetime.now().isoformat()),
            ended_at=data.get("ended_at"),
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AudioCache:
    """Cached audio data reference."""
    cache_key: str
    audio_hash: str
    format: str
    duration_ms: int
    size_bytes: int
    storage_path: Optional[str]  # Path to cached audio file
    cached_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "audio_hash": self.audio_hash,
            "format": self.format,
            "duration_ms": self.duration_ms,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioCache":
        return cls(
            cache_key=data["cache_key"],
            audio_hash=data["audio_hash"],
            format=data.get("format", "mp3"),
            duration_ms=data.get("duration_ms", 0),
            size_bytes=data.get("size_bytes", 0),
            storage_path=data.get("storage_path"),
            cached_at=data.get("cached_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
            hit_count=data.get("hit_count", 0),
        )
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()


class SpeechMemoryManager:
    """
    Manages memory for speech operations.
    
    Example:
        >>> speech_memory = SpeechMemoryManager()
        >>> 
        >>> # Store transcription
        >>> speech_memory.store_transcription(audio_hash, text, language="en")
        >>> 
        >>> # Get transcription history
        >>> history = speech_memory.get_transcription_history(speaker_id="user-1")
        >>> 
        >>> # Create voice profile
        >>> profile = speech_memory.create_voice_profile("John", profile_type="user")
        >>> 
        >>> # Start voice conversation
        >>> conv = speech_memory.start_conversation(["user-1", "agent-1"])
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        audio_cache_ttl: int = 3600,  # 1 hour
        max_transcription_history: int = 500,
        max_synthesis_history: int = 500,
    ):
        self.memory = memory_manager or MemoryManager()
        self.audio_cache_ttl = audio_cache_ttl
        self.max_transcription_history = max_transcription_history
        self.max_synthesis_history = max_synthesis_history
        
        # In-memory storage
        self._transcriptions: List[TranscriptionMemory] = []
        self._syntheses: List[SynthesisMemory] = []
        self._voice_profiles: Dict[str, VoiceProfile] = {}
        self._conversations: Dict[str, VoiceConversationMemory] = {}
        self._audio_cache: Dict[str, AudioCache] = {}
    
    def _hash_audio(self, audio_data: bytes) -> str:
        """Create hash from audio data."""
        return hashlib.sha256(audio_data).hexdigest()[:16]
    
    def _hash_text(self, text: str) -> str:
        """Create hash from text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    # =========================================================================
    # Transcription History
    # =========================================================================
    
    def store_transcription(
        self,
        audio_hash: str,
        text: str,
        language: str = "en",
        confidence: float = 1.0,
        provider: str = "",
        model: str = "",
        duration_ms: int = 0,
        words: List[Dict] = None,
        speaker_id: str = None,
        metadata: Dict = None,
    ) -> TranscriptionMemory:
        """Store a transcription in memory."""
        import uuid
        
        transcription = TranscriptionMemory(
            transcription_id=f"trans-{uuid.uuid4().hex[:8]}",
            audio_hash=audio_hash,
            text=text,
            language=language,
            confidence=confidence,
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            word_count=len(text.split()),
            words=words or [],
            speaker_id=speaker_id,
            metadata=metadata or {},
        )
        
        self._transcriptions.append(transcription)
        
        # Limit history
        while len(self._transcriptions) > self.max_transcription_history:
            self._transcriptions.pop(0)
        
        # Persist
        self.memory.store_long_term(
            "speech:transcriptions",
            [t.to_dict() for t in self._transcriptions[-100:]],
            priority=6,
        )
        
        return transcription
    
    def get_transcription_history(
        self,
        speaker_id: str = None,
        language: str = None,
        provider: str = None,
        last_n: int = None,
    ) -> List[TranscriptionMemory]:
        """Get transcription history."""
        if not self._transcriptions:
            data = self.memory.retrieve("speech:transcriptions", [])
            self._transcriptions = [TranscriptionMemory.from_dict(t) for t in data]
        
        history = self._transcriptions
        
        if speaker_id:
            history = [t for t in history if t.speaker_id == speaker_id]
        
        if language:
            history = [t for t in history if t.language == language]
        
        if provider:
            history = [t for t in history if t.provider == provider]
        
        if last_n:
            history = history[-last_n:]
        
        return history
    
    def search_transcriptions(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[TranscriptionMemory]:
        """Search transcriptions by text content."""
        query_lower = query.lower()
        
        results = [
            t for t in self._transcriptions
            if query_lower in t.text.lower()
        ]
        
        return results[:top_k]
    
    def get_transcription_by_audio(
        self,
        audio_hash: str,
    ) -> Optional[TranscriptionMemory]:
        """Get transcription by audio hash (for caching)."""
        for t in reversed(self._transcriptions):
            if t.audio_hash == audio_hash:
                return t
        return None
    
    # =========================================================================
    # Synthesis History
    # =========================================================================
    
    def store_synthesis(
        self,
        text: str,
        voice: str,
        provider: str = "",
        model: str = "",
        audio_format: str = "mp3",
        duration_ms: int = 0,
        audio_size_bytes: int = 0,
        metadata: Dict = None,
    ) -> SynthesisMemory:
        """Store a synthesis record."""
        import uuid
        
        synthesis = SynthesisMemory(
            synthesis_id=f"synth-{uuid.uuid4().hex[:8]}",
            text_hash=self._hash_text(text),
            text=text,
            voice=voice,
            provider=provider,
            model=model,
            audio_format=audio_format,
            duration_ms=duration_ms,
            audio_size_bytes=audio_size_bytes,
            metadata=metadata or {},
        )
        
        self._syntheses.append(synthesis)
        
        # Limit history
        while len(self._syntheses) > self.max_synthesis_history:
            self._syntheses.pop(0)
        
        # Persist
        self.memory.store_long_term(
            "speech:syntheses",
            [s.to_dict() for s in self._syntheses[-100:]],
            priority=5,
        )
        
        return synthesis
    
    def get_synthesis_history(
        self,
        voice: str = None,
        provider: str = None,
        last_n: int = None,
    ) -> List[SynthesisMemory]:
        """Get synthesis history."""
        if not self._syntheses:
            data = self.memory.retrieve("speech:syntheses", [])
            self._syntheses = [SynthesisMemory.from_dict(s) for s in data]
        
        history = self._syntheses
        
        if voice:
            history = [s for s in history if s.voice == voice]
        
        if provider:
            history = [s for s in history if s.provider == provider]
        
        if last_n:
            history = history[-last_n:]
        
        return history
    
    def get_synthesis_by_text(
        self,
        text: str,
        voice: str,
    ) -> Optional[SynthesisMemory]:
        """Get synthesis by text and voice (for caching)."""
        text_hash = self._hash_text(text)
        for s in reversed(self._syntheses):
            if s.text_hash == text_hash and s.voice == voice:
                return s
        return None
    
    # =========================================================================
    # Voice Profiles
    # =========================================================================
    
    def create_voice_profile(
        self,
        name: str,
        profile_type: str = "user",
        preferred_language: str = "en",
        voice_settings: Dict = None,
    ) -> VoiceProfile:
        """Create a voice profile."""
        import uuid
        profile_id = f"voice-{uuid.uuid4().hex[:8]}"
        
        profile = VoiceProfile(
            profile_id=profile_id,
            name=name,
            profile_type=profile_type,
            preferred_language=preferred_language,
            voice_settings=voice_settings or {},
        )
        
        self._voice_profiles[profile_id] = profile
        
        self.memory.store_long_term(
            f"speech:profile:{profile_id}",
            profile.to_dict(),
            priority=7,
        )
        
        return profile
    
    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """Get a voice profile."""
        if profile_id in self._voice_profiles:
            return self._voice_profiles[profile_id]
        
        data = self.memory.retrieve(f"speech:profile:{profile_id}")
        if data:
            profile = VoiceProfile.from_dict(data)
            self._voice_profiles[profile_id] = profile
            return profile
        
        return None
    
    def update_voice_profile(
        self,
        profile_id: str,
        **updates,
    ) -> Optional[VoiceProfile]:
        """Update a voice profile."""
        profile = self.get_voice_profile(profile_id)
        if not profile:
            return None
        
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now().isoformat()
        
        self.memory.store_long_term(
            f"speech:profile:{profile_id}",
            profile.to_dict(),
        )
        
        return profile
    
    def set_voice_embedding(
        self,
        profile_id: str,
        embedding: List[float],
    ) -> bool:
        """Set voice embedding for speaker identification."""
        profile = self.get_voice_profile(profile_id)
        if not profile:
            return False
        
        profile.embedding = embedding
        profile.sample_count += 1
        profile.updated_at = datetime.now().isoformat()
        
        self.memory.store_long_term(
            f"speech:profile:{profile_id}",
            profile.to_dict(),
        )
        
        return True
    
    def find_speaker_by_embedding(
        self,
        embedding: List[float],
        threshold: float = 0.8,
    ) -> Optional[VoiceProfile]:
        """Find speaker by voice embedding similarity."""
        best_match = None
        best_similarity = 0.0
        
        for profile in self._voice_profiles.values():
            if profile.embedding:
                # Cosine similarity
                similarity = self._cosine_similarity(embedding, profile.embedding)
                if similarity > best_similarity and similarity >= threshold:
                    best_similarity = similarity
                    best_match = profile
        
        return best_match
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    # =========================================================================
    # Voice Conversations
    # =========================================================================
    
    def start_conversation(
        self,
        participants: List[str],
        metadata: Dict = None,
    ) -> VoiceConversationMemory:
        """Start a new voice conversation."""
        import uuid
        conversation_id = f"vconv-{uuid.uuid4().hex[:8]}"
        
        conversation = VoiceConversationMemory(
            conversation_id=conversation_id,
            participants=participants,
            metadata=metadata or {},
        )
        
        self._conversations[conversation_id] = conversation
        
        self.memory.store_short_term(
            f"speech:conversation:{conversation_id}",
            conversation.to_dict(),
            ttl=7200,
            priority=6,
        )
        
        return conversation
    
    def get_conversation(
        self,
        conversation_id: str,
    ) -> Optional[VoiceConversationMemory]:
        """Get a voice conversation."""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id]
        
        data = self.memory.retrieve(f"speech:conversation:{conversation_id}")
        if data:
            conv = VoiceConversationMemory.from_dict(data)
            self._conversations[conversation_id] = conv
            return conv
        
        return None
    
    def add_conversation_turn(
        self,
        conversation_id: str,
        role: str,  # user, agent
        text: str,
        speaker_id: str = None,
        audio_id: str = None,
        duration_ms: int = 0,
    ) -> bool:
        """Add a turn to a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return False
        
        turn = {
            "role": role,
            "text": text,
            "speaker_id": speaker_id,
            "audio_id": audio_id,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
        }
        
        conv.turns.append(turn)
        conv.turn_count = len(conv.turns)
        conv.total_duration_ms += duration_ms
        
        self.memory.store_short_term(
            f"speech:conversation:{conversation_id}",
            conv.to_dict(),
            ttl=7200,
        )
        
        return True
    
    def end_conversation(
        self,
        conversation_id: str,
        summary: str = None,
    ) -> Optional[VoiceConversationMemory]:
        """End a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        
        conv.ended_at = datetime.now().isoformat()
        conv.summary = summary
        
        # Move to long-term storage
        self.memory.store_long_term(
            f"speech:conversation:{conversation_id}",
            conv.to_dict(),
            priority=5,
        )
        
        return conv
    
    def get_conversation_transcript(
        self,
        conversation_id: str,
        format: str = "text",  # text, chat, markdown
    ) -> Optional[str]:
        """Get conversation transcript."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        
        if format == "chat":
            return "\n".join([f"{t['role']}: {t['text']}" for t in conv.turns])
        elif format == "markdown":
            lines = []
            for t in conv.turns:
                if t["role"] == "user":
                    lines.append(f"**User:** {t['text']}")
                else:
                    lines.append(f"**Agent:** {t['text']}")
            return "\n\n".join(lines)
        else:
            return "\n".join([t["text"] for t in conv.turns])
    
    # =========================================================================
    # Audio Cache
    # =========================================================================
    
    def cache_audio(
        self,
        audio_data: bytes,
        format: str,
        duration_ms: int,
        storage_path: str = None,
        ttl: int = None,
    ) -> str:
        """Cache audio data."""
        audio_hash = self._hash_audio(audio_data)
        cache_key = f"audio:{audio_hash}"
        
        expires_at = None
        if ttl or self.audio_cache_ttl:
            ttl = ttl or self.audio_cache_ttl
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        
        cache_entry = AudioCache(
            cache_key=cache_key,
            audio_hash=audio_hash,
            format=format,
            duration_ms=duration_ms,
            size_bytes=len(audio_data),
            storage_path=storage_path,
            expires_at=expires_at,
        )
        
        self._audio_cache[cache_key] = cache_entry
        
        self.memory.store_short_term(
            f"speech:{cache_key}",
            cache_entry.to_dict(),
            ttl=ttl or self.audio_cache_ttl,
        )
        
        return cache_key
    
    def get_audio_cache(self, audio_hash: str) -> Optional[AudioCache]:
        """Get cached audio info."""
        cache_key = f"audio:{audio_hash}"
        
        if cache_key in self._audio_cache:
            entry = self._audio_cache[cache_key]
            if not entry.is_expired:
                entry.hit_count += 1
                return entry
            else:
                del self._audio_cache[cache_key]
        
        data = self.memory.retrieve(f"speech:{cache_key}")
        if data:
            entry = AudioCache.from_dict(data)
            if not entry.is_expired:
                entry.hit_count += 1
                self._audio_cache[cache_key] = entry
                return entry
        
        return None
    
    # =========================================================================
    # Stats & Cleanup
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get speech memory statistics."""
        total_transcription_duration = sum(t.duration_ms for t in self._transcriptions)
        total_synthesis_duration = sum(s.duration_ms for s in self._syntheses)
        
        return {
            "transcription_count": len(self._transcriptions),
            "total_transcription_duration_ms": total_transcription_duration,
            "synthesis_count": len(self._syntheses),
            "total_synthesis_duration_ms": total_synthesis_duration,
            "voice_profiles": len(self._voice_profiles),
            "active_conversations": len([c for c in self._conversations.values() if not c.ended_at]),
            "audio_cache_size": len(self._audio_cache),
        }
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired audio cache."""
        count = 0
        expired = [k for k, v in self._audio_cache.items() if v.is_expired]
        for key in expired:
            del self._audio_cache[key]
            count += 1
        return count


__all__ = [
    "TranscriptionMemory",
    "SynthesisMemory",
    "VoiceProfile",
    "VoiceConversationMemory",
    "AudioCache",
    "SpeechMemoryManager",
]
