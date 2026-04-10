import React from 'react';
import { Home, Trophy, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './StickyNav.css';

export function StickyNav() {
    const navigate = useNavigate();
    return (
        <nav className="sticky-nav glass-card">
            <button className="nav-item" onClick={() => navigate('/')}>
                <Home size={24} />
                <span>Home</span>
            </button>
            <button className="nav-item" onClick={() => navigate('/leaderboard/1')}>
                <Trophy size={24} />
                <span>Board</span>
            </button>
            <button className="nav-item" onClick={() => navigate('/admin')}>
                <User size={24} />
                <span>Admin</span>
            </button>
        </nav>
    );
}
