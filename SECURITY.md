# Security Policy

## Security Model & Data Handling

HackingUpdate is designed to process public threat intelligence feeds and deliver daily security briefings.

### API Keys & Secrets
- **Zero hardcoded credentials**: All API keys, tokens, and webhook URLs are read strictly from environment variables or `.env`.
- **Git Safety**: `.env`, runtime database files (`data/`), cache files (`cache/`), and logs (`logs/`) are explicitly excluded via `.gitignore`.
- **Character Truncation & Privacy**: Notifier payloads enforce platform character limits (e.g. 1520 chars for Twilio WhatsApp) and strip detailed internal telemetry before sending external webhooks.

## Reporting a Vulnerability

If you discover a security vulnerability within HackingUpdate, please do **NOT** open a public issue.

Instead, please send an email to the repository owner or submit a private security advisory through GitHub:
- **GitHub Security Advisory**: [Report a Vulnerability](https://github.com/4nilsj/hackingupdate/security/advisories/new)

Please include:
- A description of the issue
- Steps to reproduce
- Potential security impact
