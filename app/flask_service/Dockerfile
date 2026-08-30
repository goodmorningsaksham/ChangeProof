FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask requests tenacity prometheus_client
COPY app.py .
EXPOSE 8005
CMD ["python", "app.py"]
