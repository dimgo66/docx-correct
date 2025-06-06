FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp/ ./webapp/
COPY src/ ./src/
COPY LanguageTool-6.6/ ./LanguageTool-6.6/
COPY typograf-7.4.4/ ./typograf-7.4.4/

EXPOSE 7860

CMD ["gunicorn", "webapp.app:app", "-b", "0.0.0.0:7860"] 