import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import AdminSetup from './pages/AdminSetup';
import LiveScorecard from './pages/LiveScorecard';
import Leaderboard from './pages/Leaderboard';
import PlayRound from './pages/PlayRound';
import ViewScorecard from './pages/ViewScorecard';
import { StickyNav } from './components/layout/StickyNav';

import './styles/global.css';

function App() {
  return (
    <BrowserRouter>
      <div style={{ paddingBottom: '80px' }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/admin" element={<AdminSetup />} />
          <Route path="/match/:matchupId" element={<LiveScorecard />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/view-scorecard/:tournamentId/:teeId" element={<ViewScorecard />} />
          <Route path="/play/:tournamentId/:teeId" element={<PlayRound />} />
        </Routes>
      </div>
      <StickyNav />
    </BrowserRouter>
  );
}

export default App;
