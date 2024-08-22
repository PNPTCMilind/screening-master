FROM python:3.11-slim

WORKDIR /backend

COPY ../requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "backend.fastapi_app:app"]
