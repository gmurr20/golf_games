# Golf Competition Web App

A full-stack web application designed to host a golf competition among friends. This project features a robust back-end Match Engine that automatically calculates USGA WHS course handicaps and tracks live Match Play standings (1v1 and 2v2 formats), alongside a visually premium mobile-first frontend.

---

## 🛠 Tech Stack

- **Backend:** Python, Flask, Flask-SQLAlchemy (PostgreSQL), Pytest
- **Frontend:** React 18, Vite, React Router, Vanilla CSS (Glassmorphism design system)
- **Deployment:** Ready for Railway (Docker / Nixpacks compatibility out of the box)

---

## 📁 Project Structure

```text
golf_games/
├── backend/
│   ├── app.py              # Flask Application Factory 
│   ├── config.py           # Database URL Setup
│   ├── requirements.txt    # Python Dependencies
│   ├── models/             # SQLAlchemy ORM Models
│   │   ├── base.py
│   │   └── models.py       # Core schema (Competition, Player, Format, etc.)
│   ├── routes/             # API Endpoints (Admin, Play, Query)
│   ├── services/           
│   │   ├── handicap.py     # USGA WHS Math & Allocation Engine
│   │   └── match_engine.py # Compares pops and outputs Match Status
│   └── tests/              # Pytest suites
└── frontend/
    ├── package.json        # NPM Scripts & Dependencies
    ├── vite.config.js      # Bundler config & Backend Proxy (/api -> 8080)
    └── src/
        ├── api/backend.js  # Axios wrapper & Admin Key injection
        ├── components/     # Reusable glassy UI Components
        ├── pages/          # React Routing views
        └── styles/         # Global design system (variables.css)
```

---

## 🚀 How to Run Locally

Because the project is separated cleanly, you need to run two servers in development.

### 1. Start the Backend (Flask)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create the local SQLite Database
python -c 'from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()'

# Run the server (starts on http://localhost:8080)
python app.py
```

### 2. Start the Frontend (Vite)
Open a new terminal:
```bash
cd frontend
npm install
npm run dev
```
The frontend will start on `http://localhost:5173`. API calls to `/api/*` are automatically proxied to the Flask backend running on `8080` (configured in `vite.config.js`).

---

## 🏛 Database Architecture & Tenancy

The database model is strictly hierarchical and **multi-tenant** to allow this app to be reused by different friend groups safely.

1. **Competition**: The root tenant. Secures modifications via a lightweight `admin_key` rather than full user auth.
2. **Player**: Belongs to a Competition. Holds a raw `handicap_index`.
3. **Course / Tee / Hole**: Stores Rating, Slope, and the 1-18 relative handicap difficulty indexes required to allocate strokes per hole.
4. **Tournament**: Holds multiple games/rounds.
5. **Matchup**: Defines the actual Match (e.g. 1v1 or 2v2).
6. **Score**: Raw strokes submitted by a Player on a specific Hole for a Matchup.

---

## 🧮 Core Logic Algorithms

If you are an AI working on this base, pay close attention to `backend/services/`.

- **WHS Course Handicap:** `handicap.py` pulls the Player Index, Tee Slope, Tee Rating, and Par to calculate total pops. `Course Handicap = (Index * (Slope / 113)) + (Rating - Par)`.
- **Match Play Allocation:** In both 1v1 and 2v2, the player with the *lowest* Course Handicap is reduced to 0 strokes. Every other player's handicap is reduced by that minimum amount. 
- **Pop Distribution:** Strokes are allocated sequentially starting on the hole with `handicap_index = 1` (the hardest hole), wrapping around to 18 if a player receives more than 18 strokes.
- **Match Status:** `match_engine.py` dynamically calculates Net Scores live to determine hole winners, ties (Pushes), and outputs the status string (e.g. "Team A is 2 UP thru 14").

---

## 🤖 Notes For Future AI Agents

1. **UI Design Constraint:** The frontend utilizes plain Vanilla CSS specifically built around a Glassmorphism, mobile-first aesthetic with deep visual interaction. **DO NOT** convert this to Tailwind unless explicitly instructed by the user. Maintain the HSL color variables found in `frontend/src/styles/variables.css`.
2. **Auth Handling:** The app explicitly relies on an `admin_key` in the header for secure actions to avoid complex JWT setups. 
3. **Native Future:** Ensure React components remain modular. The user plans to wrap this Vite project in **Capacitor** allowing it to compile as a native iOS/Android application later without rewriting it in React Native. Maintain touch-target friendliness.
4. **Railway Deployment:** Railway connects both components automatically. The `.env` variables mapped on Railway to `DATABASE_URL` will cleanly convert the app from SQLite to PostgreSQL per the logic at the top of `backend/config.py`.
