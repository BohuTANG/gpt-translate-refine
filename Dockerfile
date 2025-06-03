FROM python:alpine@sha256:18159b2be11db91f84b8f8f655cd860f805dbd9e49a583ddaac8ab39bf4fe1a7

WORKDIR /app

# Install git and GitHub CLI
RUN apk add --no-cache git curl

# Configure Git to trust the GitHub workspace directory
RUN git config --global --add safe.directory /github/workspace

# Install GitHub CLI
RUN curl -sL https://github.com/cli/cli/releases/download/v2.45.0/gh_2.45.0_linux_amd64.tar.gz -o gh.tar.gz && \
    tar -xzf gh.tar.gz && \
    mv gh_*/bin/gh /usr/local/bin/ && \
    rm -rf gh_* gh.tar.gz

COPY translate.py .
COPY src/ ./src/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "/app/translate.py"]