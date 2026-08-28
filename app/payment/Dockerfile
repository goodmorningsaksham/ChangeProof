FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn==0.28.0 \
    prometheus-client==0.20.0 \
    pydantic==2.6.4

COPY main.py /app/main.py

ENV PORT=8002
EXPOSE 8002

CMD ["python", "main.py"]
