# 🤖 AI Developer & Agent Context Guide

Welcome, Agent. This guide is written to give you immediate context on this codebase, its mathematical rules, design boundaries, and engineering constraints. 

---

## 🚨 CRITICAL RULE: Self-Maintenance Directive

As an AI agent developing in this repository, you are **required to keep documentation up-to-date**. 

> [!IMPORTANT]
> **DOCUMENTATION MAINTENANCE MANDATE:**
> Whenever you implement new features, change database models, add scoring formats (e.g. scramble, stableford), modify API routes, or alter styling parameters, you **MUST immediately update the relevant documentation**:
> 1. **Database Schema updates:** Update the Mermaid ER Diagram in `backend/README.md`.
> 2. **Client Styling/UX additions:** Update `frontend/README.md` if CSS variables, Capacitor criteria, or component patterns are modified.
> 3. **Architectural boundaries:** Update this `docs/AI_DEVELOPER_GUIDE.md` if core auth patterns, tenancy mechanics, or system rules evolve.
> 
> *Do not leave documentation tasks for the human developer. Treat documentation updates as a core, blocking part of your feature implementation.*

---

## 🏛 Core Architectural Rules & Tenancy

### 1. Light Multi-Tenancy (The `Competition` Root)
* The application supports multi-tenancy. Every `Player`, `Tournament`, `Course`, and `Matchup` is associated directly or transitively with a root `Competition`.
* **Administrative Security:** There is no heavy JWT/OAuth identity provider. Security is maintained by a lightweight `admin_key` (saved as a string on `Competition`).
* **API Header Injection:** Frontend requests targeting mutating admin routes must supply the key in the HTTP headers as `X-Admin-Key`.

### 2. Variable Hole Support (Flexible Layouts)
* Historically standard 18-hole hardcoding has been systematically decoupled.
* The codebase accommodates standard 18-hole rounds, 9-hole loops, 12-hole executive setups, or custom course profiles.
* Always query holes dynamically from the `Hole` database model ordered by `Hole.hole_number`, rather than looping through range `1 to 18`.

### 3. Mathematical Integrity & WHS Standards
* Always verify WHS calculations inside `backend/services/handicap.py`.
* Ensure proper rounding (`round_half_up` to handle Bankers' rounding discrepancies) is maintained.
* Playing Handicaps are calculated *relative* to the low course handicap in a matchup, reducing the low player's handicap to `0` and deducting that baseline from other players.

### 4. Backend-First Computation Principle (Zero Frontend Parsing)
* **Rule of Thumb:** All scoring engines, handicap logic, leaderboard sorting, tiebreaks, match standing reductions, and complex statistical calculations must reside strictly in the Python backend.
* **Frontend Limitation:** The React client is purely a visual presenter and simple state gatherer. The frontend should **never** run complex parsing, handicap allocations, stroke distributions, or scoring math. It simply makes network calls to the Flask API and renders the formatted responses directly.

---

## 🎨 Frontend Styling Rules (Strictly Vanilla CSS)

* **No TailwindCSS / CSS Frameworks:** We rely purely on custom, premium Vanilla CSS classes built around HSL variables.
* **Glassmorphic Aesthetic:** Panels, cards, and dashboards utilize translucent dark layers, fine borders, and backdrop-blurs.
  * *Example standard container class styling:*
    ```css
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
    }
    ```
* **Mobile-First Touch targets:** Every active button or click handler must maintain a size footprint of at least `44px x 44px` for touch friendliness in anticipation of Capacitor native compiling.

---

## 🧪 Testing Guidelines

Before committing any modifications to calculations or database models, you **must run the automated backend pytest suite**.

### Standard Test Collection Commands
```bash
cd backend
source venv/bin/activate
python -m pytest
```

### Essential Mocking Rules
When writing or expanding unit tests using mocked models:
1. **SqlAlchemy Relationship Mocking:** Always manually bind relations. For example, because `MatchupPlayer.player` is lazy-evaluated by SQLAlchemy, mocked objects will throw an `AttributeError` when accessing `mp.player.handicap_index` unless you explicitly assign the relationship attribute:
   ```python
   # DO THIS
   mp1 = MatchupPlayer(matchup_id=1, player_id=1)
   p1 = Player(id=1, handicap_index=5.0)
   mp1.player = p1 # Bind reference
   ```
2. **Scratch Isolation:** Keep scratch testing payloads under `backend/scratch/` and prefix-less to prevent pytest from miscollecting them as tests.
