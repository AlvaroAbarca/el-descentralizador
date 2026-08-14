# Cloud Agent development image for El Descentralizador.
# Bundles the system services the app needs for a full end-to-end dev loop:
# PostgreSQL 16 (tsvector FTS), Redis (SAQ queue + sessions), uv + Python 3.14.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        sudo \
        postgresql-16 \
        postgresql-client-16 \
        redis-server \
    && rm -rf /var/lib/apt/lists/*

# The ubuntu:24.04 base image ships a non-root `ubuntu` user (uid 1000).
# Grant it passwordless sudo so the start script can manage local services.
RUN echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu

USER ubuntu
WORKDIR /home/ubuntu

# Install uv and the pinned Python 3.14 toolchain as the ubuntu user.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/ubuntu/.local/bin:${PATH}"
RUN uv python install 3.14 \
    && sudo ln -sf /home/ubuntu/.local/bin/uv /usr/local/bin/uv \
    && sudo ln -sf /home/ubuntu/.local/bin/uvx /usr/local/bin/uvx

EXPOSE 8000
