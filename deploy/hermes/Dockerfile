FROM nousresearch/hermes-agent:latest

SHELL ["/bin/bash", "-lc"]

# Install base deps + GitHub CLI (official Debian repo) + Railway CLI (npm)
RUN apt-get update && apt-get install -y wget gpg ca-certificates curl git unzip jq  && install -d -m 755 /etc/apt/keyrings /etc/apt/sources.list.d  && wget -qO /etc/apt/keyrings/githubcli.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg  && chmod a+r /etc/apt/keyrings/githubcli.gpg  && echo "deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list  && apt-get update  && apt-get install -y gh  && npm install -g @railway/cli  && curl -fsSL https://cli.supabase.com/install.sh | bash  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace

ENV PORT=3000
ENV HOST=0.0.0.0

EXPOSE 3000

CMD ["gateway", "run"]
