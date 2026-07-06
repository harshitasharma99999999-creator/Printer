# GitHub Actions Credential Setup

This file intentionally contains no credentials.

Store API keys, OAuth client secrets, and refresh tokens only in:

- GitHub repository **Settings → Secrets and variables → Actions**
- a local `.env` file that is ignored by Git
- ignored local token files such as `token.json` or `.mp/youtube_tokens/*.json`

Never paste real tokens into documentation or commit them to the repository.
If a token was previously written here, revoke and rotate it before using the
automation.

Grand Forno setup instructions are maintained in `README.md`.
