FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Coleta determinística, sem banco ou segredos de produção durante o build.
RUN python manage.py collectstatic --noinput --settings=config.static_settings \
    && groupadd --gid 10001 mediatrack \
    && useradd --uid 10001 --gid mediatrack --no-create-home mediatrack
USER mediatrack
ENV DJANGO_SETTINGS_MODULE=config.production
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "45", "--access-logfile", "-", "--error-logfile", "-"]
