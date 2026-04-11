import React from 'react';
import { Home, Trophy, User, Award } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import './StickyNav.css';

export function StickyNav() {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <nav className="sticky-nav glass-card">
            <button className={`nav-item ${isActive('/') ? 'active' : ''}`} onClick={() => navigate('/')}>
                <Home size={24} />
                <span>Home</span>
            </button>
            <button className={`nav-item ${isActive('/leaderboard') ? 'active' : ''}`} onClick={() => navigate('/leaderboard')}>
                <Trophy size={24} />
                <span>Board</span>
            </button>
            <button className={`nav-item ${isActive('/awards') ? 'active' : ''}`} onClick={() => navigate('/awards')}>
                <Award size={24} />
                <span>Awards</span>
            </button>
            <button className={`nav-item ${isActive('/admin') ? 'active' : ''}`} onClick={() => navigate('/admin')}>
                <User size={24} />
                <span>Admin</span>
            </button>
        </nav>
    );
}
