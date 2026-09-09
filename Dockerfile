FROM python:3.11-slim
WORKDIR /app
COPY activation_server_requirements.txt .
RUN pip install --no-cache-dir -r activation_server_requirements.txt
COPY activation_server.py .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python activation_server.py"]
