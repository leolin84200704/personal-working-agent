# LIS Code Agent

> Automated maintenance agent for LIS-related projects, assisting with Jira ticket processing.

## Structure

```
lis-code-agent/
├── SOUL.md           # Agent core philosophy and behavioral guidelines
├── IDENTITY.md       # Agent role and capabilities
├── USER.md           # Leo's work preferences and habits
├── MEMORY.md         # Accumulated knowledge index
├── src/              # Source code
│   ├── core/         # Core logic
│   ├── integrations/ # Jira, Git, Claude API
│   ├── memory/       # Knowledge base management system
│   └── utils/        # Utility functions
├── config/           # Configuration files
└── output/           # Generated reports and documentation
```

## Setup

1. Copy `.env.example` to `.env` and fill in configuration
2. Install dependencies: `pip install -r requirements.txt`

## Usage

```bash
# Manual scan execution
python -m src.main scan

# Update memory
python -m src.main memory show
```

## Security

Agent's Git operations are strictly restricted:
- ✅ Only create branches with `feature/leo/*` or `bugfix/leo/*` prefixes
- ✅ Only push to own branches
- ❌ No force push or merge operations

## License

Internal use only.
