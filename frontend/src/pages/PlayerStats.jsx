import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import './PlayerStats.css';

export default function PlayerStats() {
    const { playerId } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStats();
    }, [playerId]);

    const fetchStats = async () => {
        try {
            const res = await backend.get(`/players/${playerId}/stats`);
            setData(res.data);
        } catch (e) {
            console.error('Failed to fetch player stats', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="player-stats-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Fetching player history...</span>
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="player-stats-container">
                <button className="back-button" onClick={() => navigate(-1)}>← Back</button>
                <div className="list-empty">Player not found or no stats yet.</div>
            </div>
        );
    }

    const { 
        name, handicap_index, team, team_display_name,
        gross_birdies_plus, net_birdies_plus,
        wins, losses, ties, total_points,
        rounds, matchups 
    } = data;

    return (
        <div className="player-stats-container animate-slide-up">
            <header className="player-stats-header">
                <button className="back-button" onClick={() => navigate(-1)}>← Back</button>
                <h1>Player Profile</h1>
            </header>

            {/* Performance Toplines */}
            <div className="player-info-card animate-slide-up">
                <div className="player-main-info">
                    <div className="player-name-section">
                        <h2>{name}</h2>
                        <span className={`player-team-label team-${team?.toLowerCase()}`}>
                            {team_display_name || team}
                        </span>
                    </div>
                    <div className="player-handicap-badge">
                        <span className="hcp-value">{handicap_index}</span>
                        <span className="hcp-label">HCP INDEX</span>
                    </div>
                </div>

                <div className="record-summary">
                    <div className="record-block">
                        <span className="record-label">Match Record</span>
                        <span className="record-value">{wins}-{losses}-{ties}</span>
                    </div>
                    <div className="record-block">
                        <span className="record-label">Points Contributed</span>
                        <span className="record-value">{total_points.toFixed(1)} PTS</span>
                    </div>
                </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="summary-stats-grid animate-slide-up" style={{ animationDelay: '0.1s' }}>
                <div className="summary-stat-card">
                    <span className="summary-stat-value">{gross_birdies_plus}</span>
                    <span className="summary-stat-label">Gross Birdie+</span>
                </div>
                <div className="summary-stat-card">
                    <span className="summary-stat-value">{net_birdies_plus}</span>
                    <span className="summary-stat-label">Net Birdie+</span>
                </div>
            </div>

            {/* Round History */}
            <section className="history-section animate-slide-up" style={{ animationDelay: '0.15s' }}>
                <h3 className="history-title">⛳ Round History</h3>
                <div className="history-list">
                    {rounds.length === 0 ? (
                        <div className="list-empty">No rounds recorded yet.</div>
                    ) : (
                        rounds.map((r, i) => (
                            <div 
                                key={i} 
                                className="round-history-item"
                                onClick={() => {
                                    const params = new URLSearchParams();
                                    if (r.tee_time) params.set('tee_time', r.tee_time);
                                    navigate(`/view-scorecard/${r.tournament_id}/${r.tee_id}?${params.toString()}`);
                                }}
                            >
                                <div className="round-info">
                                    <span className="round-course">{r.course_name}</span>
                                    <span className="round-meta">
                                        {new Date(r.tee_time).toLocaleDateString([], { month: 'short', day: 'numeric' })} • {r.completed_holes} Holes
                                    </span>
                                </div>
                                <div className="round-scores">
                                    <div className="score-block">
                                        <span className={`score-val ${r.to_par.startsWith('-') ? 'under' : r.to_par.startsWith('+') ? 'over' : ''}`}>
                                            {r.to_par}
                                        </span>
                                        <span className="score-label">GROSS</span>
                                    </div>
                                    <div className="score-block">
                                        <span className={`score-val ${r.net_to_par.startsWith('-') ? 'under' : r.net_to_par.startsWith('+') ? 'over' : ''}`}>
                                            {r.net_to_par}
                                        </span>
                                        <span className="score-label">NET</span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>

            {/* Matchup History */}
            <section className="history-section animate-slide-up" style={{ animationDelay: '0.2s' }}>
                <h3 className="history-title">⚔️ Matchup History</h3>
                <div className="history-list">
                    {matchups.length === 0 ? (
                        <div className="list-empty">No matchups played yet.</div>
                    ) : (
                        matchups.map((m, i) => (
                            <div key={m.id} className="matchup-history-item">
                                <span className="matchup-course">{m.course_name} • {m.format.replace('_', ' ')}</span>
                                <div className="matchup-main">
                                    <span className="matchup-opponents">vs {m.opponents.join(' & ')}</span>
                                    <span className={`matchup-result-badge ${
                                        m.result.includes('Won') || m.result.includes('UP') ? 'win' : 
                                        m.result.includes('Lost') || m.result.includes('DN') ? 'loss' : 'tie'
                                    }`}>
                                        {m.result}
                                    </span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}
