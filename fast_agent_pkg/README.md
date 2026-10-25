# FastAgent Package (Legacy Compatibility Layer)

> **Notice:** FastAgent has evolved into **[OlaiEdge](https://github.com/SiddardhaShayini/OlaiEdge)** (`olaiedge`).  
> This package provides 100% backward compatibility for existing FastAgent codebases.

## Migration to OlaiEdge

If you are starting a new project, we recommend using the new primary package:

```bash
pip install olaiedge
```

```python
import olaiedge

agent = olaiedge.OlaiEngine(model_path="gemma-2b-q4.gguf")
response = agent.ask("Multiply 36 by 12")
print(response)
```

## Backward-Compatible Usage

Existing FastAgent imports continue to work seamlessly:

```python
from fast_agent import FastAgent, FastAgentEngine

agent = FastAgent(model_path="gemma-2b-q4.gguf")
response = agent.ask("Hello from FastAgent!")
print(response)
```

For full documentation on memory budgeting, slot caching, and desktop SDKs (Electron, Tauri, Flutter), visit the main **[OlaiEdge Documentation](../README.md)**.
