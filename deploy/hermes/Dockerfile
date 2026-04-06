FROM nousresearch/hermes-agent:latest

ARG TARGETARCH
SHELL ["/bin/bash", "-lc"]

# Install base deps + GitHub CLI (official Debian repo) + Railway CLI (npm) + Supabase CLI (standalone binary)
RUN apt-get update && apt-get install -y wget gpg ca-certificates curl git unzip \
 && install -d -m 755 /etc/apt/keyrings /etc/apt/sources.list.d \
 && wget -qO /etc/apt/keyrings/githubcli.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg \
 && chmod a+r /etc/apt/keyrings/githubcli.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y gh \
 && npm install -g @railway/cli \
 && ( [ "$TARGETARCH" = "amd64" ] && SUPABASE_ARCH=linux_amd64 || SUPABASE_ARCH=linux_arm64 ) \
 && SUPABASE_VERSION=$(curl -sL https://api.github.com/repos/supabase/cli/releases/latest | grep '"tag_name"' | sed -E 's/.*"v?([^"]+)".*/\1/') \
 && wget -qO /tmp/supabase.tar.gz "https://github.com/supabase/cli/releases/latest/download/supabase_${SUPABASE_VERSION}_${SUPABASE_ARCH}.tar.gz" \
 && mkdir -p /usr/local/bin \
 && tar -xzf /tmp/supabase.tar.gz -C /usr/local/bin supabase \
 && chmod +x /usr/local/bin/supabase \
 && rm -rf /var/lib/apt/lists/* /tmp/supabase.tar.gz

WORKDIR /workspace
COPY . /workspace

CMD ["gateway", "run"]
