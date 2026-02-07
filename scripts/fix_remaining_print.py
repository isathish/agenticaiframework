#!/usr/bin/env python3
"""Fix remaining print() calls in docs."""
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

# Fix specific files
fixes = {
    "TROUBLESHOOTING.md": [
        ("print([a.name for a in manager.agents])", "logger.info([a.name for a in manager.agents])"),
        ("print(tool_registry.list_tools())", "logger.info(tool_registry.list_tools())"),
        ("print(llm.list_models())", "logger.info(llm.list_models())"),
        ("print(pm.list_processes())", "logger.info(pm.list_processes())"),
    ],
    "faq.md": [
        ('print(os.getenv("OPENAI_API_KEY"))', 'logger.info(os.getenv("OPENAI_API_KEY"))'),
    ],
    "CONFIGURATION.md": [
        ('print(config.get_config("LLM"))', 'logger.info(config.get_config("LLM"))'),
        ('print(config.get_config("Logging"))', 'logger.info(config.get_config("Logging"))'),
    ],
    "tools.md": [
        ("print(json.dumps(result, indent=2))", "logger.info(json.dumps(result, indent=2))"),
        ('print(transcript["text"])', 'logger.info(transcript["text"])'),
    ],
    "deployment.md": [
        ("print(json.dumps(log_entry))", "logger.info(json.dumps(log_entry))"),
    ],
    "contributing.md": [
        ("print(result.output)", "logger.info(result.output)"),
    ],
    "performance.md": [
        ("print(s.getvalue())", "logger.info(s.getvalue())"),
    ],
    "quick-start.md": [
        ("print(response.json())", "logger.info(response.json())"),
    ],
}

count = 0
for fname, replacements in fixes.items():
    p = DOCS / fname
    if p.exists():
        text = p.read_text()
        changed = False
        for old, new in replacements:
            if old in text:
                text = text.replace(old, new)
                changed = True
                count += 1
        if changed:
            p.write_text(text)
            print(f"  Fixed: {fname}")

# Fix example files
for fname in ["research_agent.md", "customer_support_bot.md", "code_generation_pipeline.md"]:
    p = DOCS / "examples" / fname
    if p.exists():
        text = p.read_text()
        original = text
        text = re.sub(r'\bprint\("', 'logger.info("', text)
        text = re.sub(r"\bprint\(result\)", "logger.info(result)", text)
        text = re.sub(r"\bprint\(generated_code\)", "logger.info(generated_code)", text)
        text = re.sub(r"\bprint\(evaluation_result\)", "logger.info(evaluation_result)", text)
        if text != original:
            p.write_text(text)
            count += 1
            print(f"  Fixed: examples/{fname}")

print(f"\nDone! {count} additional fixes applied.")
