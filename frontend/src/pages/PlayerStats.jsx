import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import PlayerAvatar from '../components/ui/PlayerAvatar';
import './PlayerStats.css';

export default function PlayerStats() {
    const { playerId } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [compInfo, setCompInfo] = useState({ name: 'Murray Cup 2026' });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStats();
        fetchCompInfo();
    }, [playerId]);

    const fetchCompInfo = async () => {
        try {
            const res = await backend.get('/competition/active');
            setCompInfo(res.data);
        } catch (e) {
            console.error('Failed to fetch competition info', e);
        }
    };

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
        name, profile_picture, handicap_index, team, team_display_name,
        gross_birdies_plus, net_birdies_plus,
        wins, losses, ties, total_points,
        rounds, matchups, by_par 
    } = data;

    return (
        <div className="player-stats-container animate-slide-up">
            <header className="player-stats-header">
                <div className="player-stats-brand-header">
                    <div className="player-stats-brand-left">
                        <img src="/full-logo.jpg" alt="Logo" className="player-stats-logo-mini" />
                        <span className="player-stats-brand-title">Murray Cup 2026</span>
                    </div>
                    <button className="back-button" onClick={() => navigate(-1)}>← Back</button>
                </div>
                <span className="player-stats-subtitle">{compInfo.name}</span>
                <h1>Player Profile</h1>
            </header>

            {/* Performance Toplines */}
            <div className="player-info-card animate-slide-up">
                <div className="player-main-info">
                    <PlayerAvatar name={name} image={profile_picture} size="lg" />
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
                    
                    {/* Visual performance bar */}
                    {(wins + losses + ties) > 0 && (
                        <div className="record-bar">
                            <div className="record-segment win" style={{ width: `${(wins / (wins + losses + ties)) * 100}%` }}></div>
                            <div className="record-segment tie" style={{ width: `${(ties / (wins + losses + ties)) * 100}%` }}></div>
                            <div className="record-segment loss" style={{ width: `${(losses / (wins + losses + ties)) * 100}%` }}></div>
                        </div>
                    )}
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

            {/* Par Breakdown Section */}
            {by_par && Object.keys(by_par).length > 0 && (
                <section className="history-section animate-slide-up" style={{ animationDelay: '0.12s' }}>
                    <h3 className="history-title">📊 Performance by Par</h3>
                    <div className="par-cards-container">
                        {[3, 4, 5].map((par) => {
                            const parData = by_par[par.toString()];
                            if (!parData) return null;

                            const { avg_gross, avg_net, total_holes, best_gross, distances } = parData;
                            const diff = avg_gross - par;
                            const diffStr = diff > 0 ? `+${diff.toFixed(2)}` : (diff === 0 ? 'E' : `${diff.toFixed(2)}`);
                            const diffClass = diff < 0 ? 'under-par' : (diff > 0 ? 'over-par' : 'even-par');
                            
                            // Visual percentage fill for progress indicator (lower score = more filled)
                            const fillPercent = Math.min(Math.max(par / avg_gross, 0.4), 1.0);
                            const radius = 38;
                            const strokeDasharray = 2 * Math.PI * radius;
                            const strokeDashoffset = strokeDasharray * (1 - fillPercent);

                            // Logically sort distance buckets ascending by yardage
                            const distanceOrder = {
                                "< 140y": 1, "140-180y": 2, "180y+": 3,
                                "< 360y": 1, "360-420y": 2, "420y+": 3,
                                "< 500y": 1, "500-550y": 2, "550y+": 3
                            };
                            const sortedDistances = distances 
                                ? [...distances].sort((a, b) => (distanceOrder[a.range] || 0) - (distanceOrder[b.range] || 0))
                                : [];

                            return (
                                <div key={par} className="par-card glass-card">
                                    <div className="par-card-header">
                                        <span className="par-title">Par {par}'s</span>
                                        <span className={`par-diff-badge ${diffClass}`}>{diffStr}</span>
                                    </div>
                                    
                                    <div className="par-circle-wrapper">
                                        <svg className="par-circle-svg" viewBox="0 0 100 100">
                                            <circle className="circle-track" cx="50" cy="50" r={radius} />
                                            <circle 
                                                className={`circle-progress ${diffClass}`} 
                                                cx="50" 
                                                cy="50" 
                                                r={radius}
                                                strokeDasharray={strokeDasharray}
                                                strokeDashoffset={strokeDashoffset}
                                            />
                                        </svg>
                                        <div className="par-circle-center">
                                            <span className="avg-gross-value">{avg_gross.toFixed(1)}</span>
                                            <span className="avg-gross-label">AVG GROSS</span>
                                        </div>
                                    </div>

                                    <div className="par-stats-footer">
                                        <div className="par-stat-pill">
                                            <span className="pill-label">Avg Net</span>
                                            <span className="pill-value">{avg_net ? avg_net.toFixed(1) : '-'}</span>
                                        </div>
                                        <div className="par-stat-pill">
                                            <span className="pill-label">Best</span>
                                            <span className="pill-value">{best_gross}</span>
                                        </div>
                                        <div className="par-stat-pill">
                                            <span className="pill-label">Holes</span>
                                            <span className="pill-value">{total_holes}</span>
                                        </div>
                                    </div>

                                    {sortedDistances && sortedDistances.length > 0 && (
                                        <div className="par-distance-section">
                                            {sortedDistances.map((dist, idx) => {
                                                const barWidth = Math.min(Math.max(75 + 25 * (dist.avg - par), 10), 100);
                                                return (
                                                    <div key={idx} className="distance-row">
                                                        <span className="distance-range-label">{dist.range}</span>
                                                        <div className="distance-bar-bg">
                                                            <div 
                                                                className="distance-bar-fill" 
                                                                style={{ width: `${barWidth}%` }}
                                                            />
                                                        </div>
                                                        <span className="distance-avg-value">{dist.avg.toFixed(1)}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

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
                                    if (playerId) params.set('player_id', playerId);
                                    if (r.tee_time) params.set('tee_time', r.tee_time);
                                    navigate(`/view-scorecard/${r.tournament_id}/${r.tee_id}?${params.toString()}`);
                                }}
                            >
                                <div className="round-info">
                                    <span className="round-course">{r.course_name}</span>
                                    <span className="round-meta">
                                        {new Date(r.tee_time).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                                        &nbsp; {r.completed_holes} Holes
                                        <span className="round-format-tag">
                                            {r.format === 'individual' ? 'IND' : r.format?.replace('_', ' ')}
                                        </span>
                                    </span>
                                </div>
                                <div className="round-scores">
                                    <div className="score-block">
                                        <div className="score-main-row">
                                            <div className="score-val-wrapper">
                                                <span className="score-val">{r.gross_score}</span>
                                                <span className={`score-rel ${r.to_par.startsWith('-') ? 'under' : r.to_par.startsWith('+') ? 'over' : ''}`}>
                                                    {r.to_par}
                                                </span>
                                            </div>
                                        </div>
                                        <span className="score-label">GROSS</span>
                                    </div>
                                    <div className="score-block">
                                        <div className="score-main-row">
                                            <div className="score-val-wrapper">
                                                <span className="score-val">{r.net_score}</span>
                                                <span className={`score-rel ${r.net_to_par.startsWith('-') ? 'under' : r.net_to_par.startsWith('+') ? 'over' : ''}`}>
                                                    {r.net_to_par}
                                                </span>
                                            </div>
                                        </div>
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
                            <div 
                                key={m.id} 
                                className="matchup-history-item"
                                onClick={() => navigate(`/view-scorecard/${m.tournament_id}/${m.tee_id}?matchup_id=${m.id}&player_id=${playerId}`)}
                            >
                                <div className="matchup-meta-row">
                                    <span className="matchup-course">
                                        {m.course_name} • {m.format === 'individual' ? 'IND' : m.format?.replace('_', ' ')}
                                    </span>
                                    <span className="matchup-range-time">
                                        {m.hole_range} {m.tee_time_display ? `• ${m.tee_time_display}` : ''}
                                    </span>
                                </div>
                                <div className="matchup-main">
                                    <span className="matchup-opponents">
                                        {m.teammates && m.teammates.length > 0 && `(with ${m.teammates.join(' & ')}) `}
                                        vs {m.opponents.join(' & ')}
                                    </span>
                                    <span className={`matchup-result-badge ${
                                        !m.is_completed ? 'tie' :
                                        m.winner === 'Push' ? 'tie' :
                                        m.winner === m.my_team ? 'win' : 'loss'
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
