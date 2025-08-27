<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/pypi/v/agenticaiframework?color=blue&label=PyPI%20Version&logo=python&logoColor=white" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/agenticaiframework/">
    <img src="https://img.shields.io/pypi/dm/agenticaiframework?color=green&label=Downloads&logo=python&logoColor=white" alt="Downloads">
  </a>
  <a href="https://github.com/isathish/agenticaiframework/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/isathish/agenticaiframework/python-package.yml?branch=main&label=Build&logo=github" alt="Build Status">
  </a>
  <a href="https://isathish.github.io/agenticaiframework/">
    <img src="https://img.shields.io/badge/Documentation-Online-blue?logo=readthedocs&logoColor=white" alt="Documentation">
  </a>
</div>

---

## 10. Performance Issues

### Problem: Slow agent responses
**Solution:**
- Optimize prompt templates to reduce token usage.
- Use caching for repeated computations.
- Profile the code to identify bottlenecks.

---

## 11. Deployment Problems

### Problem: Application works locally but fails in production
**Solution:**
- Check environment variables are set correctly in production.
- Ensure all dependencies are installed.
- Verify network access for external APIs.

---

## 12. Memory Leaks

### Problem: Increasing memory usage over time
**Solution:**
- Clear unused memory entries.
- Use persistent storage for large datasets.
- Monitor memory usage with `monitoring.py`.

---

## 13. Debugging Tips for Complex Workflows

- Break workflows into smaller steps.
- Use verbose logging.
- Test each component in isolation.

---

## 14. Getting Community Support

- Join the GitHub Discussions page.
- Ask questions on Stack Overflow with the `agenticaiframework` tag.
- Contribute to the documentation with your own troubleshooting tips.
# AgenticAI Troubleshooting Guide

This guide lists common issues you may encounter when using **AgenticAI** and how to resolve them.

---

## 1. Installation Issues

### Problem: `ModuleNotFoundError: No module named 'agenticaiframework'`
**Solution:**
- Ensure you have installed the package:
```bash
pip install agenticaiframework
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
