# Contributing to HackingUpdate

Thank you for considering contributing to HackingUpdate! We welcome contributions to feed sources, notification channels, AI prompt tuning, and core pipeline optimizations.

## Getting Started

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/4nilsj/hackingupdate.git
   cd hackingupdate
   ```

2. **Set up Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```

## Development Guidelines

### Adding New RSS/Atom Feeds
Add valid RSS or Atom feed URLs directly to `feeds/feeds.txt`:
```txt
https://example.com/security-feed.xml
```

### Adding New Notification Channels
Notification step modules live in `scripts/` (e.g. `scripts/slack_notifier.py`). To add a channel:
1. Create a script module following the pattern in `scripts/teams_notifier.py`.
2. Add the corresponding environment variables to `.env.example` and `config.py`.
3. Register the new step in `hackingupdate/pipeline.py` within `PIPELINE_STEPS`.

### Code Style
- Follow PEP 8 guidelines.
- Use explicit type hints where applicable.
- Ensure all sensitive data (API keys, webhook URLs, phone numbers) are passed via environment variables only.

## Pull Request Process

1. Create a descriptive feature branch (`git checkout -b feature/slack-notifier`).
2. Commit your changes with clear, concise messages.
3. Test locally using `hackingupdate run`.
4. Open a Pull Request targeting the `main` branch.
