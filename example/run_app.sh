#!/bin/bash
# Startup script for Vaccination Game on PythonAnywhere

echo "================================"
echo "🎮 VACCINATION GAME - STARTUP"
echo "================================"

# Set environment variables
export DB_HOST=GameTheoryUDE26.mysql.eu.pythonanywhere-services.com
export DB_USER=GameTheoryUDE26
export DB_PASSWORD=UDE2020EM
export DB_NAME='GameTheoryUDE26$vaccination_game'
export DB_PORT=3306

export ADMIN_PASSWORD=admin123  # Change this!
export SECRET_KEY=change_me_in_production_to_something_random
export FLASK_DEBUG=1

echo "📊 DB: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo "🔒 Admin Password: $ADMIN_PASSWORD"
echo "================================"

# Run the app
python app_vaccination.py
