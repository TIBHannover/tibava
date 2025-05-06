FROM python:3.10


WORKDIR /app/analyser/inference/

COPY ./requirements.txt /app/analyser/inference/
RUN pip install -r requirements.txt

COPY ./src/ /app/analyser/inference/
COPY ./deploy.yml /app/analyser/deploy.yml

RUN mkdir -p /data
# Switching to a non-root user, please refer to https://aka.ms/vscode-docker-python-user-rights
RUN useradd appuser 
RUN chown -R appuser /data
USER appuser




ENV PYTHONPATH="/app/"
# Run the binary
# CMD ["python3", "/app/src/main.py", "-v"]
CMD ["serve", "run", "/app/analyser/deploy.yml"]
