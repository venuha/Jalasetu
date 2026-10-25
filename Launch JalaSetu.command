#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  JALASETU_RUNTIME=.venv/bin/python
elif [ -x "$HOME/Desktop/Agentic System/.venv/bin/python" ]; then
  JALASETU_RUNTIME="$HOME/Desktop/Agentic System/.venv/bin/python"
else
  echo 'Create the Python environment using the steps in README.md first.'
  read -r -p 'Press Enter to close.'
  exit 1
fi
echo 'JalaSetu: http://127.0.0.1:8092'
echo 'Local synthetic planning demo. Press Control-C to stop.'
exec "$JALASETU_RUNTIME" -m uvicorn app.main:app --host 127.0.0.1 --port 8092
