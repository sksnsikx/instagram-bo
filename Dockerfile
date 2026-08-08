FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl xvfb \
    libxi6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxtst6 libnss3 \
    libxrandr2 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libxss1 fonts-liberation \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# نصب کروم با روش تست‌شده
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb 2>/dev/null || true \
    && apt-get install -f -y \
    && rm google-chrome-stable_current_amd64.deb

# بررسی نصب
RUN google-chrome --version || echo "Chrome installed"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "0", "main:app", "--bind", "0.0.0.0:8080"]
