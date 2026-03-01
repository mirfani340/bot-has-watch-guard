# Security Policy

## Supported versions

This project is currently maintained from the default branch only.

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Report privately to the maintainers with:

- A clear description of the issue
- Reproduction steps or proof of concept
- Potential impact
- Suggested remediation if available

If you reported a vulnerability, allow reasonable time for validation and patching before public disclosure.

## Secrets and operational safety

- Never commit `.env` or API tokens.
- Rotate credentials immediately if accidental exposure is suspected.
- Before making repositories public, verify history does not contain leaked secrets.