FROM ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
USER root
RUN apt-get update && apt-get install -y --no-install-recommends nginx && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --index-url https://pypi.org/simple pymysql cryptography
COPY bootstrap.py /render-bootstrap.py
COPY nginx.conf /etc/nginx/nginx.conf
CMD ["python", "/render-bootstrap.py"]
