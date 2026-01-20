---
title: Speech Processing
description: Full-featured speech-to-text and text-to-speech capabilities for voice-enabled agents
---

# 🎤 Speech Processing

AgenticAI Framework provides comprehensive speech processing capabilities including speech-to-text (STT), text-to-speech (TTS), and voice interaction management.

---

## 🎯 Overview

<div class="grid cards" markdown>

-   :microphone:{ .lg } **Speech-to-Text**

    ---

    Transcribe audio to text using multiple providers

    [:octicons-arrow-right-24: Learn STT](#speech-to-text)

-   :speaker:{ .lg } **Text-to-Speech**

    ---

    Generate natural speech from text

    [:octicons-arrow-right-24: Learn TTS](#text-to-speech)

-   :studio_microphone:{ .lg } **Real-time Processing**

    ---

    Stream audio processing for live conversations

    [:octicons-arrow-right-24: Learn Streaming](#real-time-streaming)

-   :brain:{ .lg } **Voice Memory**

    ---

    Store and retrieve voice interaction data

    [:octicons-arrow-right-24: Learn Memory](#speech-memory)

</div>

---

## 🔊 Supported Providers

| Provider | STT | TTS | Languages | Best For |
|----------|-----|-----|-----------|----------|
| **OpenAI Whisper** | ✅ | ❌ | 99+ | High accuracy, multilingual |
| **Google Cloud** | ✅ | ✅ | 125+ | Enterprise, real-time |
| **Azure Cognitive** | ✅ | ✅ | 100+ | Enterprise, custom voices |
| **Amazon (Transcribe/Polly)** | ✅ | ✅ | 75+ | AWS integration |
| **ElevenLabs** | ❌ | ✅ | 29 | Ultra-realistic voices |
| **Deepgram** | ✅ | ❌ | 36+ | Real-time, low latency |

---

## Speech-to-Text

### Basic Transcription

```python
from agenticaiframework.speech import SpeechToText

# Initialize STT
stt = SpeechToText(provider="openai")

# Transcribe audio file
result = stt.transcribe("audio.wav")
print(f"Text: {result.text}")
print(f"Language: {result.language}")
print(f"Confidence: {result.confidence:.2f}")
```

### Provider Configuration

=== "OpenAI Whisper"
    ```python
    from agenticaiframework.speech import SpeechToText, OpenAISTTConfig
    
    config = OpenAISTTConfig(
        model="whisper-1",
        language="en",  # Optional, auto-detect if not set
        temperature=0.0,
        response_format="verbose_json"
    )
    
    stt = SpeechToText(provider="openai", config=config)
    ```

=== "Google Cloud"
    ```python
    from agenticaiframework.speech import SpeechToText, GoogleSTTConfig
    
    config = GoogleSTTConfig(
        language_code="en-US",
        model="latest_long",
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        use_enhanced=True
    )
    
    stt = SpeechToText(provider="google", config=config)
    ```

=== "Azure"
    ```python
    from agenticaiframework.speech import SpeechToText, AzureSTTConfig
    
    config = AzureSTTConfig(
        region="eastus",
        language="en-US",
        profanity_option="masked",
        enable_dictation=True
    )
    
    stt = SpeechToText(provider="azure", config=config)
    ```

=== "Deepgram"
    ```python
    from agenticaiframework.speech import SpeechToText, DeepgramSTTConfig
    
    config = DeepgramSTTConfig(
        model="nova-2",
        language="en",
        smart_format=True,
        punctuate=True,
        diarize=True
    )
    
    stt = SpeechToText(provider="deepgram", config=config)
    ```

### Word-Level Timestamps

```python
result = stt.transcribe(
    "audio.wav",
    include_timestamps=True
)

for word in result.words:
    print(f"{word.text}: {word.start_time:.2f}s - {word.end_time:.2f}s")
```

### Speaker Diarization

```python
result = stt.transcribe(
    "meeting.wav",
    enable_diarization=True,
    num_speakers=3
)

for segment in result.segments:
    print(f"[Speaker {segment.speaker}] {segment.text}")
```

### Audio Formats

```python
# Supported formats
supported = stt.get_supported_formats()
# ['wav', 'mp3', 'flac', 'ogg', 'webm', 'm4a']

# Transcribe from bytes
with open("audio.wav", "rb") as f:
    audio_bytes = f.read()
    
result = stt.transcribe_bytes(
    audio_bytes,
    format="wav"
)

# Transcribe from URL
result = stt.transcribe_url("https://example.com/audio.wav")
```

---

## Text-to-Speech

### Basic Synthesis

```python
from agenticaiframework.speech import TextToSpeech

# Initialize TTS
tts = TextToSpeech(provider="openai")

# Generate speech
audio = tts.synthesize("Hello! How can I help you today?")

# Save to file
audio.save("output.mp3")

# Get audio bytes
audio_bytes = audio.to_bytes()
```

### Provider Configuration

=== "OpenAI"
    ```python
    from agenticaiframework.speech import TextToSpeech, OpenAITTSConfig
    
    config = OpenAITTSConfig(
        model="tts-1-hd",  # or "tts-1" for faster
        voice="alloy",    # alloy, echo, fable, onyx, nova, shimmer
        speed=1.0,        # 0.25 to 4.0
        response_format="mp3"
    )
    
    tts = TextToSpeech(provider="openai", config=config)
    ```

=== "ElevenLabs"
    ```python
    from agenticaiframework.speech import TextToSpeech, ElevenLabsConfig
    
    config = ElevenLabsConfig(
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model_id="eleven_multilingual_v2",
        stability=0.5,
        similarity_boost=0.75,
        style=0.5,
        use_speaker_boost=True
    )
    
    tts = TextToSpeech(provider="elevenlabs", config=config)
    ```

=== "Google Cloud"
    ```python
    from agenticaiframework.speech import TextToSpeech, GoogleTTSConfig
    
    config = GoogleTTSConfig(
        language_code="en-US",
        voice_name="en-US-Neural2-A",
        speaking_rate=1.0,
        pitch=0.0,
        audio_encoding="MP3"
    )
    
    tts = TextToSpeech(provider="google", config=config)
    ```

=== "Azure"
    ```python
    from agenticaiframework.speech import TextToSpeech, AzureTTSConfig
    
    config = AzureTTSConfig(
        region="eastus",
        voice_name="en-US-JennyNeural",
        speaking_rate=1.0,
        pitch="+0Hz",
        style="cheerful"
    )
    
    tts = TextToSpeech(provider="azure", config=config)
    ```

### Available Voices

```python
# List available voices
voices = tts.list_voices()

for voice in voices:
    print(f"ID: {voice.id}")
    print(f"Name: {voice.name}")
    print(f"Language: {voice.language}")
    print(f"Gender: {voice.gender}")
    print("---")

# Filter by language
english_voices = tts.list_voices(language="en")
```

### SSML Support

```python
# Use SSML for advanced control
ssml = """
<speak>
  <prosody rate="slow" pitch="+2st">
    Welcome to the AgenticAI Framework.
  </prosody>
  <break time="500ms"/>
  <emphasis level="strong">This is important!</emphasis>
</speak>
"""

audio = tts.synthesize_ssml(ssml)
```

### Streaming TTS

```python
# Stream audio chunks for real-time playback
async for chunk in tts.stream("This is a long text that will be streamed..."):
    await play_audio_chunk(chunk)
```

---

## Real-time Streaming

### Live Transcription

```python
from agenticaiframework.speech import RealtimeSTT

# Initialize real-time STT
realtime_stt = RealtimeSTT(provider="deepgram")

# Process audio stream
async def process_microphone():
    async with realtime_stt.stream() as stream:
        # Send audio chunks
        async for audio_chunk in microphone.record():
            await stream.send(audio_chunk)
            
            # Receive interim results
            if stream.has_result():
                result = await stream.receive()
                if result.is_final:
                    print(f"Final: {result.text}")
                else:
                    print(f"Interim: {result.text}", end="\r")
```

### Voice Activity Detection

```python
from agenticaiframework.speech import VoiceActivityDetector

vad = VoiceActivityDetector(
    sensitivity=0.5,  # 0.0 to 1.0
    min_speech_duration=0.25,
    min_silence_duration=0.5
)

async for audio_chunk in microphone.record():
    if vad.is_speech(audio_chunk):
        # Process speech
        transcription = await stt.transcribe_chunk(audio_chunk)
    else:
        # Silence detected
        if vad.is_end_of_speech():
            # User finished speaking
            process_complete_utterance()
```

### Bidirectional Voice Chat

```python
from agenticaiframework.speech import VoiceChat

# Create voice chat session
chat = VoiceChat(
    stt_provider="deepgram",
    tts_provider="elevenlabs",
    agent=my_agent
)

# Run voice conversation
async def voice_conversation():
    await chat.start()
    
    try:
        while True:
            # Listen for user speech
            user_text = await chat.listen()
            print(f"User: {user_text}")
            
            # Get agent response
            response = await chat.respond(user_text)
            print(f"Agent: {response}")
            
            # Speak response
            await chat.speak(response)
            
    except KeyboardInterrupt:
        await chat.stop()
```

---

## Speech Memory

### SpeechMemoryManager

```python
from agenticaiframework import SpeechMemoryManager

# Initialize speech memory
speech_memory = SpeechMemoryManager()

# Store transcript
speech_memory.store_transcript(
    session_id="voice_001",
    speaker="user",
    text="What's the weather like today?",
    timestamp="2024-01-15T10:30:00Z",
    audio_metadata={
        "duration_ms": 2500,
        "sample_rate": 16000,
        "format": "wav"
    }
)

# Store agent response
speech_memory.store_transcript(
    session_id="voice_001",
    speaker="agent",
    text="The weather today is sunny with a high of 72°F.",
    timestamp="2024-01-15T10:30:05Z",
    tts_metadata={
        "voice": "alloy",
        "model": "tts-1-hd"
    }
)

# Get conversation history
history = speech_memory.get_conversation(session_id="voice_001")
```

### Voice Profiles

```python
# Store voice profile for user
speech_memory.store_voice_profile(
    user_id="user_123",
    profile={
        "voice_embedding": voice_embedding,  # For speaker recognition
        "language": "en-US",
        "accent": "american",
        "speaking_rate": 1.2,
        "preferred_tts_voice": "nova",
        "preferred_tts_speed": 1.0
    }
)

# Get user's voice preferences
profile = speech_memory.get_voice_profile(user_id="user_123")

# Use profile for personalized TTS
tts = TextToSpeech(
    provider="openai",
    voice=profile["preferred_tts_voice"],
    speed=profile["preferred_tts_speed"]
)
```

### Session Analytics

```python
# Get session metrics
metrics = speech_memory.get_session_metrics(session_id="voice_001")

print(f"Total duration: {metrics.total_duration_ms}ms")
print(f"User speaking time: {metrics.user_speaking_time_ms}ms")
print(f"Agent speaking time: {metrics.agent_speaking_time_ms}ms")
print(f"Turn count: {metrics.turn_count}")
print(f"Average turn length: {metrics.avg_turn_length_ms}ms")
print(f"Silence percentage: {metrics.silence_percentage:.1%}")
```

---

## Voice-Enabled Agents

### Creating a Voice Agent

```python
from agenticaiframework import Agent, AgentConfig
from agenticaiframework.speech import VoiceCapabilities

# Configure voice capabilities
voice = VoiceCapabilities(
    stt_provider="openai",
    tts_provider="elevenlabs",
    tts_voice="rachel",
    enable_vad=True,
    streaming=True
)

# Create voice-enabled agent
agent = Agent(
    config=AgentConfig(
        name="voice_assistant",
        role="Voice Assistant",
        goal="Help users through natural voice conversations",
        voice=voice
    )
)

# Voice interaction
transcript = await agent.listen()
response = agent.execute(transcript)
await agent.speak(response.output)
```

### Multi-Modal Agent

```python
from agenticaiframework import Agent, AgentConfig

# Agent that handles both text and voice
agent = Agent(
    config=AgentConfig(
        name="multimodal_assistant",
        role="Multi-Modal Assistant",
        modalities=["text", "voice"]
    )
)

# Process based on input type
if input_type == "voice":
    transcript = await agent.listen()
    response = agent.execute(transcript)
    await agent.speak(response.output)
else:
    response = agent.execute(text_input)
    print(response.output)
```

---

## Audio Utilities

### Audio Conversion

```python
from agenticaiframework.speech import AudioConverter

converter = AudioConverter()

# Convert format
mp3_audio = converter.convert(
    input_path="audio.wav",
    output_format="mp3",
    bitrate="128k"
)

# Resample audio
resampled = converter.resample(
    audio_data,
    source_rate=44100,
    target_rate=16000
)

# Normalize volume
normalized = converter.normalize(audio_data, target_db=-20)
```

### Audio Chunking

```python
from agenticaiframework.speech import AudioChunker

chunker = AudioChunker(
    chunk_duration_ms=1000,
    overlap_ms=100
)

# Chunk audio for processing
chunks = chunker.chunk(audio_data)

for chunk in chunks:
    result = await stt.transcribe_chunk(chunk)
```

---

## Error Handling

### Retry Logic

```python
from agenticaiframework.speech import SpeechToText, STTError

stt = SpeechToText(
    provider="openai",
    max_retries=3,
    retry_delay=1.0
)

try:
    result = stt.transcribe("audio.wav")
except STTError as e:
    if e.is_rate_limit:
        print("Rate limited, waiting...")
        await asyncio.sleep(e.retry_after)
    elif e.is_audio_error:
        print(f"Audio error: {e.message}")
    else:
        raise
```

### Fallback Providers

```python
from agenticaiframework.speech import SpeechToText, FallbackChain

# Configure fallback chain
stt = SpeechToText(
    primary_provider="openai",
    fallback_chain=FallbackChain([
        "google",
        "azure",
        "deepgram"
    ])
)

# Automatically falls back on failure
result = stt.transcribe("audio.wav")
print(f"Transcribed using: {result.provider}")
```

---

## Best Practices

### 1. Choose the Right Provider

```python
# High accuracy, async processing
stt = SpeechToText(provider="openai")  # Whisper

# Real-time, low latency
stt = SpeechToText(provider="deepgram")

# Enterprise features, custom models
stt = SpeechToText(provider="azure")
```

### 2. Optimize Audio Quality

```python
from agenticaiframework.speech import AudioPreprocessor

preprocessor = AudioPreprocessor(
    noise_reduction=True,
    normalize=True,
    target_sample_rate=16000
)

# Preprocess before transcription
clean_audio = preprocessor.process(audio_data)
result = stt.transcribe_bytes(clean_audio)
```

### 3. Handle Long Audio

```python
# For long audio files, use chunked processing
from agenticaiframework.speech import LongAudioProcessor

processor = LongAudioProcessor(
    stt=stt,
    chunk_duration=30,  # 30 second chunks
    overlap=2  # 2 second overlap
)

result = await processor.transcribe("long_recording.wav")
```

---

## 📚 API Reference

For complete API documentation, see:

- [SpeechToText API](API_REFERENCE.md#speechtotext)
- [TextToSpeech API](API_REFERENCE.md#texttospeech)
- [SpeechMemoryManager API](API_REFERENCE.md#speechmemorymanager)
- [VoiceCapabilities API](API_REFERENCE.md#voicecapabilities)
