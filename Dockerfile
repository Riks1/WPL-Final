FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p instance logs
ENV PYTHONUNBUFFERED=1 PORT=7860
EXPOSE 7860
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 run:app
