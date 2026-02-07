# ── Base: Python 3.12 on Debian Bookworm ──────────────────────────────
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# ── System Dependencies ───────────────────────────────────────────────
# Remove stale Yarn repo (ships with expired GPG key in MS base images)
RUN rm -f /etc/apt/sources.list.d/yarn.list 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    curl \
    wget \
    # PostgreSQL client (for psql, pg_dump, etc.)
    postgresql-client \
    # Useful CLI tools
    jq \
    httpie \
    tree \
    ripgrep \
    fd-find \
    bat \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python: Install core packages globally for DX ─────────────────────
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt

# ── Shell: Make bat/fd available by expected names ────────────────────
RUN ln -sf /usr/bin/batcat /usr/local/bin/bat \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd

# ── Non-root user setup ──────────────────────────────────────────────
# Pre-create .vscode-server so named volume inherits correct ownership
RUN mkdir -p /home/vscode/.vscode-server && chown -R vscode:vscode /home/vscode/.vscode-server

USER vscode

# ── Shell config ─────────────────────────────────────────────────────
RUN echo 'alias ll="ls -alF"' >> ~/.zshrc \
    && echo 'alias gst="git status"' >> ~/.zshrc \
    && echo 'alias be="cd /workspace/backend"' >> ~/.zshrc \
    && echo 'alias fe="cd /workspace/frontend"' >> ~/.zshrc \
    && echo 'alias logs="docker compose logs -f"' >> ~/.zshrc \
    && echo 'export PATH="/workspace/frontend/node_modules/.bin:$PATH"' >> ~/.zshrc

RUN mkdir -p /home/vscode/.cache && chown -R vscode:vscode /home/vscode/.cache


WORKDIR /workspace
