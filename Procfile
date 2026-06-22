web: gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT webapp:app
worker: python influx_logger.py
