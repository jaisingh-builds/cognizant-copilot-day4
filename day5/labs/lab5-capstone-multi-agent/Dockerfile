FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "semantic-kernel>=1.10.0" \
    "azure-ai-agents>=1.0.0" \
    "azure-ai-projects>=1.0.0b5" \
    "azure-identity>=1.17.0" \
    "openai>=1.50.0" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "requests>=2.32.0" \
    "python-dotenv>=1.0.0"

# Mirror the host repo layout so researcher.py / analyst.py path-walks work
COPY lab1-semantic-kernel-setup /app/labs/lab1-semantic-kernel-setup
COPY lab2-orchestration-patterns /app/labs/lab2-orchestration-patterns
COPY lab5-capstone-multi-agent /app/labs/lab5-capstone-multi-agent

WORKDIR /app/labs/lab5-capstone-multi-agent
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8080"]
