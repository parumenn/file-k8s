FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# K8sのServiceに合わせてポート80を開放
EXPOSE 80
CMD ["python", "app.py"]
