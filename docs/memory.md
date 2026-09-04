---
title: Memory
description: The seven memory managers in agenticaiframework.memory - MemoryManager tiers with TTL and consolidation, AgentMemoryManager conversation/working/facts/episodes, and the workflow, orchestration, knowledge, tool and speech managers.
tags:
  - memory
---

# Memory

`agenticaiframework.memory` stores what agents and their surrounding systems accumulate over time. `MemoryManager` is a thread-safe three-tier key/value store (short-term with TTL, long-term, external) with LRU/priority eviction, search and consolidation. Six specialised managers build on the same ideas for particular kinds of data: agent conversations and facts, workflow steps and checkpoints, inter-agent messages and handoffs, embedding and query caches, tool execution history, and speech transcriptions. All of them are in-process and need no external service; pass a shared `MemoryManager` to a specialised manager when you want its entries to be visible in one place. For durable snapshots and backends (file, Redis) see [State](state.md); for the per-call token window see [Context](context.md).

## At a glance

| Class | Purpose |
|---|---|
| `MemoryManager(short_term_limit=100, long_term_limit=1000)` | Tiered key/value store: `store`, `retrieve`, `search`, `consolidate`, `get_stats`, `export_to_json` |
| `AgentMemoryManager(agent_id, ...)` | Conversation turns, working memory with TTL, learned facts, episodes |
| `WorkflowMemoryManager(...)` | Per-workflow variables, step results, checkpoints, execution history |
| `OrchestrationMemoryManager(...)` | Team shared context, agent-to-agent messages, handoffs, contributions |
| `KnowledgeMemoryManager(...)` | Embedding cache, query-result cache, retrieval history, document tracking |
| `ToolMemoryManager(...)` | Tool result cache, execution history, per-tool performance stats, argument suggestions |
| `SpeechMemoryManager(...)` | Transcription and synthesis history, audio cache, voice profiles |
| `MemoryEntry`, `MemoryStats`, `MemoryType` | Entry dataclass, counters and the `CONVERSATION/WORKING/EPISODIC/SEMANTIC/PROCEDURAL` enum |
| `memory_manager` | Module-level `MemoryManager` instance |

## Quick example

```python
from agenticaiframework.memory import MemoryManager, AgentMemoryManager

memory = MemoryManager()
memory.store("user_pref", "concise answers", memory_type="long_term", metadata={"user": "alice"})
print(memory.retrieve("user_pref"))                       # concise answers
print([entry.key for entry in memory.search("concise")])  # ['user_pref']

agent_memory = AgentMemoryManager("agent_001")
agent_memory.add_turn("user", "What's the weather like?")
agent_memory.add_turn("assistant", "Sunny, 22 C.")
agent_memory.set_working("current_task", "weather_query", ttl_seconds=300)
agent_memory.learn_fact("preference", "User prefers Celsius")     # category first
agent_memory.record_episode("weather_query", "success", summary="answered from cache")

print(agent_memory.get_conversation_text())
print([f.content for f in agent_memory.search_facts("celsius")])
print(agent_memory.get_stats())
# {'agent_id': 'agent_001', 'conversation_turns': 2, 'working_items': 1, 'episodes': 1, 'facts': 1, 'total_tokens': 0}
```

## MemoryManager

### Tiers

| Tier | Default TTL | Limit | Eviction |
|---|---|---|---|
| `short_term` | 300 s | `short_term_limit` (100) | Lowest priority first (heap), then least recently used |
| `long_term` | none | `long_term_limit` (1000) | Same rule |
| `external` | none | unlimited | none; intended as a staging area for entries you persist elsewhere |

```python
from agenticaiframework.memory import MemoryManager

memory = MemoryManager(short_term_limit=500, long_term_limit=5000)

memory.store("session:42", {"step": 3}, memory_type="short_term", ttl=60, priority=1)
memory.store("policy", "refunds within 5 days", memory_type="long_term", priority=5,
             metadata={"source": "handbook"})
memory.store_short_term("scratch", [1, 2, 3])                 # ttl=300, priority=0
memory.store_long_term("brand_voice", "plain, direct")        # ttl=None, priority=5
memory.store_external("s3://bucket/report.pdf", {"etag": "abc"})

print(memory.retrieve("policy"))                              # searches short_term, long_term, external
print(memory.retrieve("missing", default="n/a"))
print(memory.get_memory("long_term", "policy"))               # tier-specific read

hits = memory.search("refund", memory_type="long_term")       # substring match on key, value and metadata
print([(e.key, e.priority, e.access_count) for e in hits])

memory.consolidate()          # entries read 5+ times move from short_term to long_term with priority + 2
print(memory.get_stats())
# {'total_stores': 5, 'total_retrievals': 3, 'cache_hits': 2, 'cache_misses': 1, 'evictions': 0,
#  'expirations': 0, 'hit_rate': 0.67, 'short_term_count': 2, 'long_term_count': 2, 'external_count': 1}

memory.export_to_json("/tmp/memory_dump.json")
memory.clear("short_term")    # or clear_short_term() / clear_long_term() / clear_external() / clear_all()
```

`retrieve` refreshes `accessed_at` and `access_count` on the entry, drops it if the TTL has expired (counted in `expirations`) and records a hit or miss in `stats`. `MemoryEntry` fields: `key`, `value`, `ttl`, `priority`, `metadata`, `created_at`, `accessed_at`, `access_count`; methods `is_expired()`, `access()`, `to_dict()`, `from_dict()`. The legacy `set_memory(memory_type, key, value)` / `get_memory(memory_type, key, default)` / `clear_memory(memory_type)` accept `"short"`, `"long"` or `"external"` as tier names. All public methods hold an internal lock.

## AgentMemoryManager

Per-agent memory in four parts, each with a cap: conversation turns (`max_conversation_turns=100`), working memory (`max_working_items=50`), episodes (`max_episodes=500`) and facts (`max_facts=1000`).

```python
from agenticaiframework.memory import AgentMemoryManager

mem = AgentMemoryManager("support_agent", max_conversation_turns=200)

# Conversation
mem.add_turn("system", "You help with billing.", tokens=6)
mem.add_turn("user", "I was charged twice.", metadata={"channel": "chat"})
mem.add_turn("assistant", "I can see two authorisations; one will drop off.")
print(mem.get_conversation(last_n=2, roles=["user", "assistant"])[0].role)   # user
print(mem.get_conversation_text(format="simple"))                             # role: content lines
print(mem.summarize_conversation()[:40])       # default summariser truncates; pass summarizer=fn for an LLM

# Working memory with relevance and TTL
mem.set_working("ticket_id", "T-1042", relevance=1.0, ttl_seconds=900)
mem.set_working("last_intent", "refund", relevance=0.6)
mem.decay_working_memory(decay_rate=0.3)       # relevance *= (1 - rate); items below 0.1 are dropped
print(mem.get_working("ticket_id"), mem.get_all_working())

# Facts
fact = mem.learn_fact("preference", "Prefers email over phone", source="ticket T-1042", confidence=0.9)
mem.use_fact(fact.fact_id)                     # bumps use_count / last_used
print([f.content for f in mem.get_facts(category="preference", min_confidence=0.5)])
print([f.content for f in mem.search_facts("email", top_k=3)])
mem.forget_fact(fact.fact_id)

# Episodes
mem.record_episode(
    task="refund_request", outcome="success", summary="Refunded duplicate charge",
    actions=["lookup_invoice", "issue_refund"], learnings=["check auth holds first"], importance=0.8,
)
print([e.task for e in mem.get_episodes(outcome="success", min_importance=0.5)])
print([e.summary for e in mem.get_relevant_episodes("duplicate refund", top_k=2)])

snapshot = mem.export_all()                    # {'agent_id', 'conversation', 'working', 'episodes', 'facts', 'exported_at'}
mem.clear_working(); mem.clear_conversation(); mem.clear_all()
```

Dataclasses: `ConversationTurn(turn_id, role, content, timestamp, metadata, tokens)`, `WorkingMemoryItem(key, value, relevance, created_at, expires_at)`, `Fact(fact_id, category, content, source, confidence, learned_at, last_used, use_count)`, `Episode(episode_id, task, outcome, summary, actions, learnings, timestamp, importance, metadata)`. `search_facts` and `get_relevant_episodes` score by word overlap between the query and the stored text. If a `memory_manager` is supplied, facts and episodes are mirrored into its long-term tier.

## WorkflowMemoryManager

Tracks variables, step results and checkpoints for multi-step workflows so a run can be resumed or audited.

```python
from agenticaiframework.memory import WorkflowMemoryManager, StepResultType

wf = WorkflowMemoryManager(max_checkpoints_per_workflow=10, max_execution_history=100)

ctx = wf.create_context("etl-2026-09", initial_variables={"batch_size": 100})
wf.set_variable("etl-2026-09", "region", "eu")
print(wf.get_variable("etl-2026-09", "batch_size"), wf.get_all_variables("etl-2026-09"))

wf.record_step_result("etl-2026-09", "s1", "load", output=[1, 2, 3], duration_ms=40)
wf.record_step_result("etl-2026-09", "s2", "validate", error="schema mismatch", duration_ms=5)
print(wf.get_step_output("etl-2026-09", "s1"))                    # [1, 2, 3]
print(wf.get_last_step_result("etl-2026-09").result_type)         # StepResultType.ERROR

total = wf.pass_output_to_next("etl-2026-09", from_step="s1", to_step="s3", transform=sum)
print(total, wf.get_step_input("etl-2026-09", "s3"))              # 6 6
print(wf.aggregate_outputs("etl-2026-09", ["s1"], aggregator=lambda outs: len(outs)))

checkpoint = wf.checkpoint("etl-2026-09", current_step=2)
restored = wf.restore_from_checkpoint("etl-2026-09")              # latest, or pass checkpoint_id=
print(restored.current_step, len(restored.step_results))

wf.record_execution("etl-2026-09", "Nightly ETL", status="failed", total_steps=3, completed_steps=1,
                    started_at="2026-09-04T01:00:00", total_duration_ms=45, error="schema mismatch")
print([r.status for r in wf.get_execution_history(status="failed")])
print(wf.get_stats())          # {'active_workflows': 1, 'total_checkpoints': 1, 'execution_history_size': 1}
wf.cleanup_workflow("etl-2026-09")
```

`StepResult.result_type` is `StepResultType.OUTPUT`, `ERROR`, `SKIP` or `PENDING`. `WorkflowContext` holds `variables`, `step_outputs` and `errors`; `WorkflowMemoryCheckpoint` snapshots the context plus step results; `WorkflowExecutionRecord` summarises one run.

## OrchestrationMemoryManager

Shared state for teams: a `SharedContext` per team, a mailbox per agent, handoff records and per-task contributions.

```python
from agenticaiframework.memory import OrchestrationMemoryManager

orch = OrchestrationMemoryManager(max_messages_per_agent=100, max_handoffs=500)

orch.create_team_context("content_team", goal="Publish the Q3 briefing",
                         initial_variables={"deadline": "Friday"}, constraints=["no external links"])
orch.update_team_variable("content_team", "status", "drafting")
orch.add_shared_knowledge("content_team", "Legal approved the numbers")
orch.update_progress("content_team", task_id="draft", progress={"percent": 40})
print(orch.get_team_variable("content_team", "deadline"), orch.get_team_context("content_team").knowledge)

msg = orch.send_message("researcher", "writer", {"facts": 3}, priority="high", message_type="handoff")
orch.broadcast_message("lead", "content_team", ["researcher", "writer"], "Standup in 5")
print(orch.get_unread_count("writer"), [m.content for m in orch.get_messages("writer", unread_only=True)])
orch.mark_read("writer", msg.message_id)

handoff = orch.record_handoff("researcher", "writer", task_id="draft", task_description="Write section 2",
                              context={"sources": ["a", "b"]}, reason="research complete")
print([h.task_id for h in orch.get_pending_handoffs("writer")])
orch.acknowledge_handoff(handoff.handoff_id, "writer")
orch.complete_handoff(handoff.handoff_id)

orch.record_contribution("writer", "draft", contribution_type="text", content="Section 2 v1")
print(orch.aggregate_contributions("draft", contribution_type="text"))
print(orch.get_handoff_history(agent_id="writer")[0].completed, orch.get_stats())
orch.cleanup_team("content_team")
```

`MessagePriority` is `LOW`, `NORMAL`, `HIGH`, `URGENT`; `send_message` and `broadcast_message` take the lowercase string. Dataclasses: `AgentMessage`, `TaskHandoff`, `SharedContext`, `AgentContribution`.

## KnowledgeMemoryManager

Caches for the RAG pipeline plus a record of what was retrieved and how well it did.

```python
from agenticaiframework.memory import KnowledgeMemoryManager

km = KnowledgeMemoryManager(embedding_cache_ttl=86_400, query_cache_ttl=3_600, max_retrieval_history=1000)

km.cache_embedding("refund policy", [0.12, 0.98, 0.33], model="text-embedding-3-small")
print(km.get_cached_embedding("refund policy", model="text-embedding-3-small"))
km.batch_cache_embeddings(["a", "b"], [[0.1], [0.2]], model="text-embedding-3-small")
vectors, missing_indexes = km.get_cached_embeddings_batch(["a", "zzz"], model="text-embedding-3-small")
print(len(vectors), missing_indexes)                          # 2 [1]

km.cache_query_result("how do refunds work", [{"text": "Refunds take 5 days", "score": 0.91}], kb_id="policies")
print(km.get_cached_query_result("how do refunds work", kb_id="policies"))

record = km.record_retrieval("how do refunds work", kb_id="policies",
                             results=[{"score": 0.91}], latency_ms=18, agent_id="support")
km.add_retrieval_feedback(record.retrieval_id, "relevant")     # relevant | partial | irrelevant
print(km.get_retrieval_stats(kb_id="policies"))

km.track_document("handbook.pdf", source_path="/docs/handbook.pdf", doc_type="pdf", chunk_count=42, total_tokens=18_000)
km.access_document("handbook.pdf")
print([d.doc_id for d in km.get_frequently_accessed_docs(top_k=5)], km.get_cache_stats())

km.invalidate_query_cache(kb_id="policies")
km.clear_embedding_cache(model="text-embedding-3-small")
print(km.cleanup_expired())                                   # {'embeddings': n, 'queries': n}
```

## ToolMemoryManager

Result caching keyed by tool name and arguments, execution history and derived statistics.

```python
from agenticaiframework.memory import ToolMemoryManager

tm = ToolMemoryManager(default_cache_ttl=3600, max_execution_history=1000)

tm.record_execution("WebSearchTool", {"query": "battery recycling"}, result={"hits": 12},
                    success=True, execution_time_ms=340, agent_id="researcher")
tm.record_execution("WebSearchTool", {"query": "lithium"}, result=None, success=False,
                    error="timeout", execution_time_ms=5000)
tm.cache_result("WebSearchTool", {"query": "battery recycling"}, {"hits": 12}, execution_time_ms=340)

print(tm.get_cached_result("WebSearchTool", {"query": "battery recycling"}))    # {'hits': 12}
print(tm.get_last_result("WebSearchTool", agent_id="researcher"))

stats = tm.get_performance_stats("WebSearchTool")
print(stats.total_executions, stats.success_rate, stats.avg_time_ms, stats.cache_hit_rate)
print(tm.get_slow_tools(threshold_ms=1000), tm.get_failing_tools(threshold=0.1))
print([p.common_args for p in tm.get_common_patterns("WebSearchTool")])
print(tm.suggest_args("WebSearchTool", partial_args={}))
print(len(tm.get_similar_executions("WebSearchTool", {"query": "battery"}, top_k=3)))
print(tm.get_execution_history(tool_name="WebSearchTool", success_only=True, last_n=5)[0].result)

tm.invalidate_cache(tool_name="WebSearchTool")
print(tm.cleanup_expired(), tm.get_memory_stats())
```

`ToolPerformanceStats` has `total_executions`, `successful_executions`, `failed_executions`, `min/max/avg_time_ms`, `cache_hits`, `cache_misses` and the `success_rate` / `cache_hit_rate` properties; `get_all_stats()` returns one per tool.

## SpeechMemoryManager

History for speech-to-text and text-to-speech calls, an audio cache and voice profiles. See [Speech](speech.md) for the providers that produce this data.

```python
from agenticaiframework.memory import SpeechMemoryManager

sm = SpeechMemoryManager(audio_cache_ttl=3600, max_transcription_history=500, max_synthesis_history=500)

t = sm.store_transcription("sha256:abc", "turn left at the next junction", language="en",
                           confidence=0.96, provider="openai", model="whisper-1", duration_ms=2100)
print(sm.get_transcription_by_audio("sha256:abc").word_count)              # 6
print([x.text for x in sm.search_transcriptions("junction", top_k=5)])
print(len(sm.get_transcription_history(language="en", provider="openai")))

s = sm.store_synthesis("Turn left ahead", voice="alloy", provider="openai", model="tts-1",
                       audio_format="mp3", duration_ms=1500, audio_size_bytes=24_000)
print(sm.get_synthesis_by_text("Turn left ahead", voice="alloy").synthesis_id == s.synthesis_id)

key = sm.cache_audio(b"\x00\x01", format="wav", duration_ms=10, storage_path="/tmp/a.wav")
profile = sm.create_voice_profile("Ada", profile_type="user", preferred_language="en")
sm.set_voice_embedding(profile.profile_id, [0.2, 0.4, 0.4])
print(sm.find_speaker_by_embedding([0.2, 0.4, 0.4], threshold=0.9).name)  # Ada
sm.update_voice_profile(profile.profile_id, speaking_rate=1.1)
print(sm.get_stats())
```

Dataclasses: `TranscriptionMemory`, `SynthesisMemory`, `VoiceProfile`, `VoiceConversationMemory`, `AudioCache`.

## Sharing one MemoryManager

Every specialised manager accepts `memory_manager=` and, when given one, mirrors its records into that store's long-term tier under prefixed keys. That makes one `search()` cover everything and one `export_to_json()` dump it all.

```python
from agenticaiframework.memory import MemoryManager, AgentMemoryManager, ToolMemoryManager

shared = MemoryManager(long_term_limit=10_000)
agent_mem = AgentMemoryManager("agent_001", memory_manager=shared)
tool_mem = ToolMemoryManager(memory_manager=shared)

agent_mem.learn_fact("preference", "User prefers Celsius")
tool_mem.record_execution("WeatherTool", {"city": "Oslo"}, {"temp": 12}, execution_time_ms=80)
print(shared.get_stats()["long_term_count"] >= 1)
```

## API summary

| Symbol | Signature / key methods | Notes |
|---|---|---|
| `MemoryManager` | `MemoryManager(short_term_limit=100, long_term_limit=1000)`; `store(key, value, memory_type="short_term", ttl=None, priority=0, metadata=None)`, `store_short_term`, `store_long_term`, `store_external`, `retrieve(key, default=None)`, `get_memory(tier, key, default)`, `search(query, memory_type=None) -> List[MemoryEntry]`, `consolidate()`, `get_stats()`, `export_to_json(path)`, `clear(memory_type=None)` | Thread-safe; `short_term`, `long_term`, `external` attributes are the underlying dicts |
| `AgentMemoryManager` | `AgentMemoryManager(agent_id, memory_manager=None, max_conversation_turns=100, max_working_items=50, max_episodes=500, max_facts=1000)`; `add_turn`, `get_conversation`, `get_conversation_text`, `summarize_conversation`, `set_working(key, value, relevance=1.0, ttl_seconds=None)`, `get_working`, `get_all_working`, `decay_working_memory(decay_rate=0.1)`, `learn_fact(category, content, source=None, confidence=1.0)`, `get_facts`, `search_facts`, `use_fact`, `forget_fact`, `record_episode(task, outcome, summary=None, actions=None, learnings=None, importance=0.5, metadata=None)`, `get_episodes`, `get_relevant_episodes(task, top_k=5)`, `get_stats`, `export_all`, `clear_*` | |
| `WorkflowMemoryManager` | `WorkflowMemoryManager(memory_manager=None, max_checkpoints_per_workflow=10, max_execution_history=100)`; `create_context`, `set_variable`, `get_variable`, `get_all_variables`, `record_step_result`, `get_step_output`, `get_step_input`, `get_last_step_result`, `get_all_step_results`, `pass_output_to_next`, `aggregate_outputs`, `checkpoint`, `get_latest_checkpoint`, `restore_from_checkpoint`, `record_execution`, `get_execution_history`, `get_stats`, `cleanup_workflow` | |
| `OrchestrationMemoryManager` | `OrchestrationMemoryManager(memory_manager=None, max_messages_per_agent=100, max_handoffs=500)`; `create_team_context`, `update_team_variable`, `get_team_variable`, `add_shared_knowledge`, `update_progress`, `get_team_context`, `send_message`, `broadcast_message`, `get_messages`, `get_unread_count`, `mark_read`, `record_handoff`, `get_pending_handoffs`, `acknowledge_handoff`, `complete_handoff`, `get_handoff_history`, `record_contribution`, `get_task_contributions`, `aggregate_contributions`, `get_stats`, `cleanup_team` | |
| `KnowledgeMemoryManager` | `KnowledgeMemoryManager(memory_manager=None, embedding_cache_ttl=86400, query_cache_ttl=3600, max_retrieval_history=1000)`; `cache_embedding`, `get_cached_embedding`, `batch_cache_embeddings`, `get_cached_embeddings_batch`, `clear_embedding_cache`, `cache_query_result`, `get_cached_query_result`, `invalidate_query_cache`, `record_retrieval`, `add_retrieval_feedback`, `get_retrieval_history`, `get_retrieval_stats`, `track_document`, `access_document`, `get_document_info`, `get_frequently_accessed_docs`, `get_cache_stats`, `cleanup_expired` | |
| `ToolMemoryManager` | `ToolMemoryManager(memory_manager=None, default_cache_ttl=3600, max_execution_history=1000)`; `cache_result`, `get_cached_result`, `invalidate_cache`, `record_execution`, `get_execution_history`, `get_last_result`, `get_similar_executions`, `get_common_patterns`, `suggest_args`, `get_performance_stats`, `get_all_stats`, `get_slow_tools`, `get_failing_tools`, `cleanup_expired`, `get_memory_stats` | |
| `SpeechMemoryManager` | `SpeechMemoryManager(memory_manager=None, audio_cache_ttl=3600, max_transcription_history=500, max_synthesis_history=500)`; `store_transcription`, `get_transcription_by_audio`, `search_transcriptions`, `get_transcription_history`, `store_synthesis`, `get_synthesis_by_text`, `get_synthesis_history`, `cache_audio`, `get_audio_cache`, `cleanup_expired_cache`, `create_voice_profile`, `get_voice_profile`, `update_voice_profile`, `set_voice_embedding`, `find_speaker_by_embedding`, `start_conversation`, `add_conversation_turn`, `get_conversation`, `get_conversation_transcript`, `end_conversation`, `get_stats` | |
| `MemoryEntry`, `MemoryStats`, `MemoryType` | dataclasses / enum | `MemoryStats.hit_rate` property |

## Related

- [State](state.md): checkpoints, snapshots, recovery and file/Redis backends
- [Context](context.md): the token-bounded context window used inside a single call
- [Agents](agents.md): `ConversationManager` for LLM-formatted history
- [Knowledge](knowledge.md), [Tools](tools.md), [Speech](speech.md), [Orchestration](orchestration.md): the subsystems the specialised managers record
