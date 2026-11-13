FROM python:3.11-slim

WORKDIR /app

# Install standard dependencies if needed
COPY . /app

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV TZ=America/New_York

CMD ["python", "trader/autonomous_engine.py"]
