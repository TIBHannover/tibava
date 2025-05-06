# For more information, please refer to https://aka.ms/vscode-docker-python
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt update --fix-missing -y && apt install python3-pip npm git libsndfile1-dev python3-numba python3-opencv python3-psycopg2 python3-numpy ffmpeg  libmariadbclient-dev-compat imagemagick python3-sklearn -y


EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1
ENV NUMBA_CACHE_DIR=/tmp/

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt


WORKDIR /app
COPY . /app

# Switching to a non-root user, please refer to https://aka.ms/vscode-docker-python-user-rights
RUN useradd appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "backend:app", "--log-level debug", "--workers=8"]
# CMD ["python", "backend.py"]
