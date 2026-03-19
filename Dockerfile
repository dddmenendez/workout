FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY crossfit_coach/ crossfit_coach/

RUN pip install --no-cache-dir .

EXPOSE 8000

# Start both API server and Telegram bot
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
