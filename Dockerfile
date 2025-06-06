FROM python:3.10-slim

WORKDIR /app

# Установить Node.js и npm (LTS)
RUN apt-get update \
    && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp/ ./webapp/
COPY src/ ./src/
COPY LanguageTool-6.6/ ./LanguageTool-6.6/
COPY typograf-7.4.4/ ./typograf-7.4.4/

# Установить pandoc и необходимые системные зависимости
RUN apt-get update && apt-get install -y pandoc && rm -rf /var/lib/apt/lists/*

COPY tools/ ./tools/

EXPOSE 7860

CMD ["gunicorn", "webapp.app:app", "-b", "0.0.0.0:7860"] 