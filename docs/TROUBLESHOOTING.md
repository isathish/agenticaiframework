# AgenticAI Troubleshooting Guide

This guide lists common issues you may encounter when using **AgenticAI** and how to resolve them.

---

## 1. Installation Issues

### Problem: `ModuleNotFoundError: No module named 'agenticaiframeworkframework'`
**Solution:**
- Ensure you have installed the package:
```bash
pip install agenticaiframeworkframework
```
- If installing from source:
```bash
pip install .
```

---

## 2. API Key Errors

### Problem: `Invalid API key` or `Authentication failed`
**Solution:**
- Check that your API key is correct.
- Set it via environment variable or configuration:
```bash
export AGENTICAI_API_KEY=your_api_key_here
```

---

## 3. Agent Not Found

### Problem: `ValueError: Agent 'xyz' not found`
**Solution:**
- Ensure the agent is registered in `hub.py` using `register_agent()`.
- Check for typos in the agent name.

---

## 4. Tool Not Found

### Problem: `ValueError: Tool 'abc' not found`
**Solution:**
- Ensure the tool is registered in `hub.py` using `register_tool()`.
- Verify the tool name matches exactly.

---

## 5. LLM Provider Errors

### Problem: `Provider not supported`
**Solution:**
- Check `llm_provider` in configuration.
- Ensure the provider is implemented in `llms.py`.

---

## 6. Memory Issues

### Problem: Data not persisting
**Solution:**
- Check the configured memory backend.
- For persistent storage, implement a custom backend.

---

## 7. Process Execution Errors

### Problem: `Process 'xyz' not found`
**Solution:**
- Ensure the process is defined in `processes.py`.
- Verify the process name is correct.

---

## 8. Debugging Tips

- Set `log_level` to `"DEBUG"` in configuration for detailed logs.
- Use `print()` statements or logging to trace execution.
- Run tests with:
```bash
pytest -v
```

---

## 9. Getting Help

- Check the [USAGE.md](USAGE.md) and [EXTENDING.md](EXTENDING.md) guides.
- Open an issue on the [GitHub repository](https://github.com/isathish/AgenticAI/issues).
