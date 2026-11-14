# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | ✅        |
| < 0.3   | ❌        |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.

Instead, email the maintainers directly or use GitHub's private vulnerability reporting feature.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to understand and address the issue.

## Scope

This policy covers the gaotai codebase. Third-party dependencies (PyYAML, Playwright) have their own security policies.

## Security Design Principles

- **No auto-publish**: The system never publishes content without explicit user action
- **Local-first**: All data stays on the user's machine; no cloud sync by default
- **No credentials in repo**: API keys and tokens are never stored in tracked files
- **Atomic writes**: File operations use write-to-temp-then-rename to prevent corruption