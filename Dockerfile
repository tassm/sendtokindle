FROM python:3.12-slim

# Pinned upstream Pandoc release; TARGETARCH (amd64 | arm64) is set by BuildKit.
ARG PANDOC_VERSION=3.12
ARG TARGETARCH
ADD https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-1-${TARGETARCH}.deb /tmp/pandoc.deb
RUN dpkg -i /tmp/pandoc.deb && rm /tmp/pandoc.deb

RUN useradd --system --uid 10001 app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/

USER app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "sendtokindle"]
