#!/bin/bash
# start_app.sh

# Function to clean up background processes safely when you hit Ctrl+C
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "Done!"
    exit 0
}

# Trap the script exit to run the cleanup function
trap cleanup SIGINT SIGTERM

echo "Starting Backend (Flask) on port 8080..."
cd backend
source venv/bin/activate

# Optional: You can keep the DB init line here if you want it to run on every boot
# python -c 'from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()'

python app.py &
BACKEND_PID=$!

echo "Starting Frontend (Vite) on port 5173..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "🔥 Golf Competition App is running! Press [Ctrl+C] to gracefully stop both servers."
wait
