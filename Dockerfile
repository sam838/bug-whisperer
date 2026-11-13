# Bug Whisperer, hosted: the website + Kane CLI (real Chrome) + Claude Code + the clinic sample app.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

# Google Chrome (Kane drives it), Node.js (Kane CLI and Claude Code), git (the repair loop diffs code)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates git fonts-liberation fonts-noto-color-emoji \
 && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends google-chrome-stable nodejs \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g @testmuai/kane-cli@0.10.4 @anthropic-ai/claude-code

# In a container Chrome runs as root, which needs --no-sandbox. Kane CLI picks Chrome up from here.
RUN printf '#!/bin/sh\nexec /usr/bin/google-chrome-stable --no-sandbox --disable-dev-shm-usage "$@"\n' \
      > /usr/local/bin/chrome-for-kane && chmod +x /usr/local/bin/chrome-for-kane
ENV KANE_CLI_CHROME_PATH=/usr/local/bin/chrome-for-kane \
    WHISPERER_HOSTED=1

WORKDIR /app
COPY requirements.txt ./
COPY clinic/requirements.txt ./clinic-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r clinic-requirements.txt

COPY . .
# The repair loop diffs the fixer's changes with git, so the image is its own small repository.
RUN git init -q && git add -A \
 && git -c user.name=bug-whisperer -c user.email=demo@localhost commit -qm "deployed snapshot" \
 && chmod +x deploy/start.sh

CMD ["./deploy/start.sh"]
