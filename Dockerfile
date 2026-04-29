FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Example run:
# docker run --rm -e OLLAMA_HOST=http://host.docker.internal:11434 \
#   -v ${PWD}:/app autorecupera python prueba_ollama.py informe_audatex.pdf
CMD ["python", "prueba_ollama.py", "informe_audatex.pdf"]
