FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        jq \
        zip \
        make && \
    pip install --no-cache-dir awscli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY . .

CMD ["make"]
