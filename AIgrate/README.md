<p align="right">
  <a href="README.zh.md">简体中文</a> | <strong>English</strong>
</p>

# AIgrate

A CLI-based AI resource pool manager. Aggregate multiple API providers, manage models centrally, and route requests intelligently.

## Features

- **Pool Mode** — Group multiple API keys into a pool with automatic failover, rate limiting, concurrency control, and circuit breaking
- **Smart Routing** — Distribute requests across keys with weight-aware and rate-aware routing
- **Rate Limiting** — Sliding window limiter (requests/time/tokens)
- **Multi-Protocol** — OpenAI, Azure, Anthropic, Hugging Face

## Quick Start

```bash
pip install -r requirements.txt
# edit `data\pools.json`
python main.py
```

## Project Structure

```
AI池/
├── main.py            # Entry point, starts REPL
├── src/
│   ├── cli/           # CLI layer (REPL, editor, printer)
│   └── core/          # Business logic (models, router, limiter, client)
├── test/              # Tests
├── docs/              # Design docs (Chinese)
└── data/              # Persistence
```

## License

MIT
