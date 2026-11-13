#!/bin/sh
# Start Bug Whisperer on the hosted demo. Secrets come from Render's environment settings.
set -e

if [ -n "$LT_USERNAME" ] && [ -n "$LT_ACCESS_KEY" ]; then
  # Basic auth for Kane CLI: no browser on a server. The key never goes to Claude or the clinic app.
  kane-cli login --username "$LT_USERNAME" --access-key "$LT_ACCESS_KEY" </dev/null \
    || echo "Kane CLI login failed: live cases will show as inconclusive"
else
  echo "LT_USERNAME / LT_ACCESS_KEY not set: live cases will show as inconclusive"
fi

if [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "No CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY: Claude can't read reports or repair"
fi

exec python -m uvicorn whisperer.web:app --host 0.0.0.0 --port "${PORT:-8000}"
