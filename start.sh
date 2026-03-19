#!/bin/bash
# Start the Telegram bot in background and the API server in foreground
python -m crossfit_coach.telegram_bot &
uvicorn crossfit_coach.api:app --host 0.0.0.0 --port ${PORT:-8000}
