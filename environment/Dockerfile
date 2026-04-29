# Main Container image for the checkdb-readiness task.
#
# This image pre-installs everything the agent needs to do its job EXCEPT
# Docker itself. Installing Docker (Engine + Compose plugin) is part of the
# task, so it must remain absent from this image.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# --- Base utilities Ansible relies on ----------------------------------------
# curl, ca-certificates, gnupg, lsb-release : apt-key / apt repo configuration
# python3 + venv + pip                       : Ansible runtime
# sudo                                       : Ansible become escalation
# iproute2, procps, less, vim-tiny           : basic diagnostics for the agent
# git                                        : occasionally pulled by roles
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        python3 \
        python3-pip \
        python3-venv \
        sudo \
        iproute2 \
        procps \
        less \
        vim-tiny \
        git \
    && rm -rf /var/lib/apt/lists/*

# --- Node.js 20.x (LTS) for building the provided NestJS skeleton -----------
# We install Node here so the NestJS image build does not have to fetch it
# again at runtime. The version is pinned via the NodeSource setup_20.x script.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version \
    && npm --version

# --- Ansible (pinned via pip, not apt, for determinism) ----------------------
# We use a venv to avoid PEP 668 "externally-managed-environment" complaints
# on Ubuntu 24.04. Symlink ansible binaries onto PATH for convenience.
RUN python3 -m venv /opt/ansible-venv \
    && /opt/ansible-venv/bin/pip install --upgrade "pip==24.2" \
    && /opt/ansible-venv/bin/pip install \
        "ansible-core==2.17.6" \
        "ansible==10.6.0" \
        "docker==7.1.0" \
        "requests==2.32.3" \
    && ln -s /opt/ansible-venv/bin/ansible /usr/local/bin/ansible \
    && ln -s /opt/ansible-venv/bin/ansible-playbook /usr/local/bin/ansible-playbook \
    && ln -s /opt/ansible-venv/bin/ansible-galaxy /usr/local/bin/ansible-galaxy \
    && ln -s /opt/ansible-venv/bin/ansible-config /usr/local/bin/ansible-config \
    && ansible --version

# --- Place the provided NestJS skeleton at /app/service/ --------------------
# The agent reads this directory but must NOT modify it (per instruction.md).
COPY service /app/service

# Reasonable default working directory; agent's own files (playbook, compose,
# etc.) will live alongside the provided service/ folder.
WORKDIR /app