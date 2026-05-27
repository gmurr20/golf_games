# 💻 React + Vite Frontend Client

Welcome to the frontend client of the Golf Competition Web App. This application is designed with a premium, mobile-first aesthetic built around modular components and seamless touch-friendly interactions.

---

## 🎨 Design System & Aesthetics (Glassmorphism)

This app features a custom **Glassmorphism Design System** configured entirely in **Vanilla CSS**. 

> [!IMPORTANT]
> **STYLING CONSTRAINT:** Do not install or introduce TailwindCSS or other CSS utility libraries unless explicitly requested. All styling tokens are maintained as HSL global variables.

### Key CSS Variables (`src/styles/variables.css`)
Our premium aesthetic relies on soft gradients, backdrop blurs, and glassy borders. The primary themes are based on these base colors:
* **Background Canvas:** Deep dark gray/blue HSL palettes.
* **Glass Panels:** `rgba(255, 255, 255, 0.05)` coupled with `backdrop-filter: blur(12px)` and a subtle light border `1px solid rgba(255, 255, 255, 0.08)`.
* **Harmonious Accents:** Teal, emerald, and vibrant gold gradients represent pars, birdies, and leading match positions instead of generic flat red/green/blue selectors.

---

## 📁 Directory Architecture

```text
frontend/
├── package.json        # NPM Scripts, React, and Vite settings
├── vite.config.js      # Bundles assets and proxies API calls (/api -> http://localhost:8080)
├── public/             # Static public assets
└── src/
    ├── main.jsx        # App entry point
    ├── App.jsx         # Root router layout
    ├── api/
    │   └── backend.js  # Axios client instance with admin_key header injectors
    ├── components/     # High-fidelity reusable glassy components
    │   ├── GlassCard.jsx
    │   ├── ScorecardRow.jsx
    │   └── LeaderboardTable.jsx
    ├── pages/          # Full page views mapped to router paths
    │   ├── Home.jsx
    │   ├── CompetitionDashboard.jsx
    │   ├── AdminSetup.jsx  # Course configurations, players addition, matchups locking
    │   └── PlayMatch.jsx   # Interactive mobile scorecard scoring flow
    └── styles/
        ├── variables.css # Theme definitions (colors, blurs, shadows, responsive sizes)
        └── global.css    # Clean global overrides and touch-scroll defaults
```

---

## ⚙️ Backend-First Computation Guideline

> [!WARNING]
> **COMPUTATION AND PARSING CONSTRAINT:**
> The React client is structurally designed to be a clean, visual presentation layer. 
> 
> Do **NOT** implement complex calculations, score processing, handicap index math, stroke distributions (pops allocation), or leaderboard parsing logic in the frontend. All complex computations, data formatting, and ranking logic are processed inside the Python Flask services on the backend. 
> 
> Keep frontend state management lightweight; simply render data payloads delivered by API endpoints.

---

## 📲 Native Compilation Readiness (Capacitor)

The entire client is constructed with mobile responsiveness in mind as it is designed to be compiled directly into an iOS/Android application utilizing **Capacitor** in future iterations.

To support this seamless compilation:
1. **Interactive Tap Targets:** Buttons, steppers, and scorecard cell editors must be at least `44px x 44px` to accommodate physical finger taps without overlap errors.
2. **Safe Area Insets:** Fixed layouts (e.g. bottom navigation bars, header tabs) must utilize CSS env variables (`safe-area-inset-bottom`, `safe-area-inset-top`) to prevent overlapping hardware notches and system gesture indicators.
3. **Optimized Scrolling:** Maintain `-webkit-overflow-scrolling: touch` properties on scorecard rows to deliver native-feeling momentum scrolling.

---

## 🚀 How to Run Locally

Install package dependencies and boot the Vite HMR dev server:
```bash
npm install
npm run dev
```
The server runs on `http://localhost:5173`. API requests targetting `/api` are automatically proxied to the Flask server (port `8080` or `5000`) based on configurations in `vite.config.js`.
