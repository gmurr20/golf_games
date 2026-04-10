import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import './Leaderboard.css';

export default function Leaderboard() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        fetchLeaderboard();
        // Poll every 60 seconds for live updates
        const interval = setInterval(fetchLeaderboard, 60000);
        return () => clearInterval(interval);
    }, []);

    const fetchLeaderboard = async () => {
        try {
            const res = await backend.get('/leaderboard');
            setData(res.data);
        } catch (e) {
            console.error('Failed to fetch leaderboard', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <div className="leaderboard-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Fetching live standings...</span>
                </div>
            </div>
        );
    }

    if (!data) return null;

    const { competition, matches, player_stats } = data;

    return (
        <div className="leaderboard-container animate-slide-up">
            <header className="leaderboard-header">
                <h1>{competition.name}</h1>
                <p>Live Standings & Match Updates</p>
            </header>

            {/* Team Scoreboard */}
            <div className="team-scoreboard animate-slide-up">
                <div className="team-score-card">
                    <span className="team-name">{competition.team_a_name}</span>
                    <span className="team-score team-a">{competition.team_a_points}</span>
                </div>
                <div className="team-score-card">
                    <span className="team-name">{competition.team_b_name}</span>
                    <span className="team-score team-b">{competition.team_b_points}</span>
                </div>
            </div>

            {/* Live Matches */}
            <section className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
                <h2 className="section-title">
                    <span className="live-indicator"></span>
                    Live Matches
                </h2>
                <div className="matches-list">
                    {matches.filter(m => m.status === 'in_progress').length === 0 ? (
                        <div className="list-empty">No active matches.</div>
                    ) : (
                        matches.filter(m => m.status === 'in_progress').map((m, i) => (
                            <MatchCard key={m.id} m={m} i={i} navigate={navigate} />
                        ))
                    )}
                </div>
            </section>

            {/* Completed Matches */}
            <section className="animate-slide-up" style={{ animationDelay: '0.15s' }}>
                <h2 className="section-title">🏁 Recent Results</h2>
                <div className="matches-list">
                    {matches.filter(m => m.status === 'completed').length === 0 ? (
                        <div className="list-empty">No final results yet.</div>
                    ) : (
                        matches.filter(m => m.status === 'completed').map((m, i) => (
                            <MatchCard key={m.id} m={m} i={i} navigate={navigate} />
                        ))
                    )}
                </div>
            </section>

            {/* Player Stats */}
            <section className="animate-slide-up" style={{ animationDelay: '0.2s' }}>
                <h2 className="section-title">🏆 Top Performers</h2>
                <div className="stats-grid">
                    {player_stats.length === 0 ? (
                        <div className="list-empty">No stats recorded yet.</div>
                    ) : (
                        player_stats.map((s, i) => (
                            <div 
                                key={s.player_id} 
                                className="stat-row animate-slide-up"
                                style={{ animationDelay: `${0.2 + (i * 0.05)}s` }}
                            >
                                <div className="stat-player-info">
                                    <span className="stat-rank">#{i + 1}</span>
                                    <span className="stat-name">{s.name}</span>
                                </div>
                                <div className="stat-value-container">
                                    <div className="stat-value">{s.birdies}</div>
                                    <div className="stat-label">Birdies+</div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}

function MatchCard({ m, i, navigate }) {
    const teamA = m.players.filter(p => p.team === 'A');
    const teamB = m.players.filter(p => p.team === 'B');
    const isLive = m.status === 'in_progress';
    const isCompleted = m.status === 'completed';

    const getHoleRangeLabel = () => {
        if (m.hole_start === 1 && m.hole_end === 9) return 'Front 9';
        if (m.hole_start === 10 && m.hole_end === 18) return 'Back 9';
        if (m.hole_start === 1 && m.hole_end === 18) return 'Full 18';
        return `Holes ${m.hole_start}-${m.hole_end}`;
    };

    return (
        <div 
            className="match-card animate-slide-up"
            style={{ animationDelay: `${0.1 + (i * 0.05)}s` }}
            onClick={() => {
                const params = new URLSearchParams();
                if (m.tee_time) params.set('tee_time', m.tee_time);
                navigate(`/view-scorecard/${m.tournament_id}/${m.tee_id}?${params.toString()}`);
            }}
        >
            <div className="match-card-header">
                <div className="match-format-group">
                    <span className="match-format">{m.format.replace('_', ' ')}</span>
                    <span className="match-range-chip">{getHoleRangeLabel()}</span>
                </div>
                <span className={`match-status-pill ${isLive ? 'live' : ''}`}>
                    {m.status_string}
                </span>
            </div>
            
            <div className="match-players">
                <div className="match-team">
                    {teamA.map(p => (
                        <div key={p.id} className="match-player-row">
                            <div className="match-player-info">
                                <span className="match-player-name">{p.name}</span>
                                <span className="match-player-team-label">{p.team_name}</span>
                            </div>
                            <span className={`match-player-to-par ${p.to_par.startsWith('-') ? 'under' : p.to_par === 'E' ? 'even' : 'over'}`}>
                                {p.to_par}
                            </span>
                        </div>
                    ))}
                </div>
                
                <span className="match-vs">vs</span>
                
                <div className="match-team" style={{ textAlign: 'right' }}>
                    {teamB.map(p => (
                        <div key={p.id} className="match-player-row reverse">
                            <div className="match-player-info">
                                <span className="match-player-name">{p.name}</span>
                                <span className="match-player-team-label">{p.team_name}</span>
                            </div>
                            <span className={`match-player-to-par ${p.to_par.startsWith('-') ? 'under' : p.to_par === 'E' ? 'even' : 'over'}`}>
                                {p.to_par}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {isCompleted && (
                <div className="match-points-awarded">
                    <span className="points-label">Points Awarded:</span>
                    <span className="points-value">
                        {m.points_a} - {m.points_b}
                    </span>
                </div>
            )}
        </div>
    );
}
