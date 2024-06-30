#!/bin/bash

# Run the Telegram authentication script
python generate_session.py

# Check if the session file was created
if [ -f /usr/src/app/session_name.session ]; then
  echo "Session file created successfully."

  # Start the Flask application
  flask run --host=0.0.0.0 --port=${PORT}
else
  echo "Failed to create session file."
  exit 1
fi
