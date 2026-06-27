FROM python:3.11-slim

# Drop to non-root for all executions
RUN groupadd -r sandbox && useradd -r -g sandbox sandbox

# No writable filesystem needed; code is passed via -c
USER sandbox
WORKDIR /tmp

ENTRYPOINT ["python"]
