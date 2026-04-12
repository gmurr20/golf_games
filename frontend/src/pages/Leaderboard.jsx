import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import PlayerAvatar from '../components/ui/PlayerAvatar';
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

    const { competition, matches } = data;

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
        </div>
    );
}

function MatchCard({ m, i, navigate }) {
    const teamA = m.players.filter(p => p.team === 'A');
    const teamB = m.players.filter(p => p.team === 'B');
    const isLive = m.status === 'in_progress';
    const isCompleted = m.status === 'completed';

    const formatTeeTime = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    };

    const getHoleRangeLabel = () => {
        if (m.hole_start === 1 && m.hole_end === 9) return 'Front 9';
        if (m.hole_start === 10 && m.hole_end === 18) return 'Back 9';
        if (m.hole_start === 1 && m.hole_end === 18) return 'Full 18';
        return `Holes ${m.hole_start}-${m.hole_end}`;
    };

    const winner = m.points_a > m.points_b ? 'A' : m.points_b > m.points_a ? 'B' : 'Push';
    const statusClass = winner === 'A' ? 'status-a' : winner === 'B' ? 'status-b' : 'status-push';

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
            <div className="match-card-context">
                <div className="match-location">
                    <span className="match-course">{m.course_name}</span>
                    <span className="match-time">
                        {formatTeeTime(m.tee_time)} • <span className="match-range-text">{getHoleRangeLabel()}</span>
                    </span>
                </div>
                <span className="match-format-chip">{m.format.replace('_', ' ')}</span>
            </div>

            <div className="match-main-row">
                <div className="match-team side-a">
                    {teamA.map(p => (
                        <div key={p.id} className="player-minimal">
                            <PlayerAvatar name={p.name} image={p.profile_picture} size="xs" />
                            <span className="player-name">{p.name}</span>
                            <span className="player-to-par-subtle">{p.to_par}</span>
                        </div>
                    ))}
                </div>

                <div className={`match-status-arrow-container ${statusClass} ${isLive ? 'live' : ''}`}>
                    <div className="match-status-arrow">
                        <span className="status-text">{m.display_value}</span>
                    </div>
                    {m.display_thru && (
                        <div className="match-thru-label">
                            {m.display_thru}
                        </div>
                    )}
                </div>

                <div className="match-team side-b">
                    {teamB.map(p => (
                        <div key={p.id} className="player-minimal">
                            <span className="player-to-par-subtle">{p.to_par}</span>
                            <span className="player-name">{p.name}</span>
                            <PlayerAvatar name={p.name} image={p.profile_picture} size="xs" />
                        </div>
                    ))}
                </div>
            </div>

            {isCompleted && (
                <div className="match-footer-line">
                    <span className={`points-status-badge ${statusClass}`}>
                        MATCH POINTS: {m.points_a} - {m.points_b}
                    </span>
                </div>
            )}
        </div>
    );
}
