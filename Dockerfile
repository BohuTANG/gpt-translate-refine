FROM python:alpine@sha256:18159b2be11db91f84b8f8f655cd860f805dbd9e49a583ddaac8ab39bf4fe1a7

WORKDIR /app

COPY translate.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "/app/translate.py"]