#!/bin/bash
# Start the FastAPI server (Telegram bot runs inside via webhook)
uvicorn crossfit_coach.api:app --host 0.0.0.0 --port ${PORT:-8000}
