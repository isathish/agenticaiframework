#!/usr/bin/env python3
"""Fix Python version refs, old typing, version strings, and print() in doc code examples."""
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
changes = []


def fix_python_version_refs():
    """Replace Python 3.8+ references with 3.10+."""
    targets = {
        "faq.md": ("- **Python**: 3.8 or higher (3.11+ recommended)",
                    "- **Python**: 3.10 or higher (3.13+ recommended)"),
        "contributing.md": ("- **Python 3.8+** (3.11+ recommended)",
                            "- **Python 3.10+** (3.13+ recommended)"),
    }
    for fname, (old, new) in targets.items():
        p = DOCS / fname
        if p.exists():
            text = p.read_text()
            if old in text:
                p.write_text(text.replace(old, new))
                changes.append(f"  {fname}: Python version updated")

    # Example files with "Compatible with Python 3.8+"
    for md in (DOCS / "examples").glob("*.md"):
        text = md.read_text()
        old = "Compatible with Python 3.8+"
        new = "Compatible with Python 3.10+"
        if old in text:
            md.write_text(text.replace(old, new))
            changes.append(f"  examples/{md.name}: Python version updated")


def fix_config_version():
    """Replace version 1.2.11 with 2.0.0 in configuration-reference.md."""
    p = DOCS / "configuration-reference.md"
    if p.exists():
        text = p.read_text()
        if '1.2.11' in text:
            p.write_text(text.replace('1.2.11', '2.0.0'))
            changes.append("  configuration-reference.md: version 1.2.11 -> 2.0.0")


def fix_old_typing_in_docs():
    """Replace Dict[...], List[...], Optional[...] with dict[...], list[...], ... | None in docs."""
    targets = ["tasks.md", "guardrails.md", "prompts.md", "security.md",
               "agents.md", "memory.md", "EXAMPLES.md", "evaluation.md",
               "communication.md", "state.md", "tools.md", "llms.md",
               "context.md", "orchestration.md", "tracing.md",
               "compliance.md", "integration.md", "infrastructure.md",
               "speech.md", "quick-start.md"]
    for fname in targets:
        p = DOCS / fname
        if not p.exists():
            continue
        text = p.read_text()
        original = text

        # Replace typing imports
        text = re.sub(r'from typing import [^\n]+\n', '', text)

        # Replace Dict[ with dict[
        text = text.replace('Dict[', 'dict[')
        # Replace List[ with list[
        text = text.replace('List[', 'list[')
        # Replace Tuple[ with tuple[
        text = text.replace('Tuple[', 'tuple[')
        # Replace Set[ with set[
        text = text.replace('Set[', 'set[')
        # Replace Optional[X] with X | None - simple cases
        text = re.sub(r'Optional\[([^\[\]]+)\]', r'\1 | None', text)

        if text != original:
            p.write_text(text)
            changes.append(f"  {fname}: modernised typing annotations")


def fix_print_in_examples():
    """Replace print(...) with logger.info(...) in Python code blocks within docs.
    
    Strategy:
    - Inside ```python ... ``` blocks, replace print(f"...") and print("...")
      with logger.info("...") or logger.info(f"...") 
    - Add 'import logging; logger = logging.getLogger(__name__)' if not present
    - Skip print() that's part of function signatures or comments
    """
    skip_files = {"processes.md", "monitoring.md", "hub.md", "knowledge.md",
                  "mcp_tools.md", "USAGE.md",  # Already rewritten
                  "COMPLETE_REDESIGN_SUMMARY.md", "DESIGN_IMPROVEMENTS.md",
                  "VISUAL_SUMMARY.md"}  # Archive docs

    for md in sorted(DOCS.glob("*.md")):
        if md.name in skip_files:
            continue
        text = md.read_text()
        original = text

        # Find python code blocks
        def replace_in_block(match):
            block = match.group(0)
            # Replace print(f"...") with logger.info(f"...")
            block = re.sub(r'\bprint\(f"', 'logger.info(f"', block)
            block = re.sub(r"\bprint\(f'", "logger.info(f'", block)
            # Replace print("...") with logger.info("...")
            block = re.sub(r'\bprint\("', 'logger.info("', block)
            block = re.sub(r"\bprint\('", "logger.info('", block)
            # Replace print(variable) — but NOT print() with no args
            block = re.sub(r'\bprint\(([a-zA-Z_][a-zA-Z0-9_.]*)\)', r'logger.info(\1)', block)
            # Replace print(variable, ...) with multiple args
            block = re.sub(r'\bprint\(([a-zA-Z_][a-zA-Z0-9_.]*),\s*', r'logger.info(\1, ', block)
            return block

        text = re.sub(r'```python\n.*?```', replace_in_block, text, flags=re.DOTALL)

        # Now add logger setup if we made changes and it's not already there
        if text != original:
            # Check if any code block needs logger import
            has_logger_info = 'logger.info(' in text
            if has_logger_info:
                # Add logger import to first python code block if not present
                def add_logger_import(match):
                    block = match.group(0)
                    if 'logger.info(' in block and 'logger = ' not in block and 'getLogger' not in block:
                        # Add import after ```python\n
                        block = block.replace(
                            '```python\n',
                            '```python\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n',
                            1
                        )
                    return block
                
                # Only add to blocks that use logger.info but don't have the import
                text = re.sub(r'```python\n.*?```', add_logger_import, text, flags=re.DOTALL)

            md.write_text(text)
            changes.append(f"  {md.name}: print() -> logger.info()")

    # Also fix examples/ subdirectory
    examples_dir = DOCS / "examples"
    if examples_dir.exists():
        for md in sorted(examples_dir.glob("*.md")):
            text = md.read_text()
            original = text

            def replace_in_block(match):
                block = match.group(0)
                block = re.sub(r'\bprint\(f"', 'logger.info(f"', block)
                block = re.sub(r"\bprint\(f'", "logger.info(f'", block)
                block = re.sub(r'\bprint\("', 'logger.info("', block)
                block = re.sub(r"\bprint\('", "logger.info('", block)
                block = re.sub(r'\bprint\(([a-zA-Z_][a-zA-Z0-9_.]*)\)', r'logger.info(\1)', block)
                return block

            text = re.sub(r'```python\n.*?```', replace_in_block, text, flags=re.DOTALL)

            if text != original:
                def add_logger_import(match):
                    block = match.group(0)
                    if 'logger.info(' in block and 'logger = ' not in block and 'getLogger' not in block:
                        block = block.replace(
                            '```python\n',
                            '```python\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n',
                            1
                        )
                    return block

                text = re.sub(r'```python\n.*?```', add_logger_import, text, flags=re.DOTALL)
                md.write_text(text)
                changes.append(f"  examples/{md.name}: print() -> logger.info()")


if __name__ == "__main__":
    print("Fixing documentation issues...")
    
    print("\n1. Python version references:")
    fix_python_version_refs()
    
    print("\n2. Configuration version:")
    fix_config_version()
    
    print("\n3. Old typing annotations:")
    fix_old_typing_in_docs()
    
    print("\n4. print() in code examples:")
    fix_print_in_examples()
    
    print(f"\nTotal changes: {len(changes)}")
    for c in changes:
        print(c)
    print("\nDone!")
