import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import './Home.css';

const STORAGE_PLAYER_ID = 'golf_player_id';
const STORAGE_PLAYER_NAME = 'golf_player_name';
const STORAGE_ACTIVE_ROUND = 'golf_active_round';

export default function Home() {
    const [playerId, setPlayerId] = useState(null);
    const [playerName, setPlayerName] = useState('');
    const [players, setPlayers] = useState([]);
    const [rounds, setRounds] = useState([]);
    const [compName, setCompName] = useState('Golf Games');
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    // Hydrate from localStorage on mount
    useEffect(() => {
        const storedId = localStorage.getItem(STORAGE_PLAYER_ID);
        const storedName = localStorage.getItem(STORAGE_PLAYER_NAME);
        if (storedId) {
            setPlayerId(parseInt(storedId));
            setPlayerName(storedName || '');
        }
        fetchCompInfo();
    }, []);

    // Fetch players (for picker) or rounds (when player is selected)
    useEffect(() => {
        if (playerId) {
            fetchRounds(playerId);
        } else {
            fetchPlayers();
        }
    }, [playerId]);

    const fetchCompInfo = async () => {
        try {
            const res = await backend.get('/competition/active');
            setCompName(res.data.name);
        } catch (e) {
            console.error('Failed to fetch competition info', e);
        }
    };

    const fetchPlayers = async () => {
        setLoading(true);
        try {
            const res = await backend.get('/players/list');
            setPlayers(res.data);
        } catch (e) {
            console.error('Failed to fetch players', e);
        } finally {
            setLoading(false);
        }
    };

    const fetchRounds = async (pid) => {
        setLoading(true);
        try {
            const res = await backend.get(`/players/${pid}/rounds`);
            setRounds(res.data);
        } catch (e) {
            console.error('Failed to fetch rounds', e);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectPlayer = (player) => {
        localStorage.setItem(STORAGE_PLAYER_ID, player.id);
        localStorage.setItem(STORAGE_PLAYER_NAME, player.name);
        setPlayerId(player.id);
        setPlayerName(player.name);
    };

    const handleChangePlayer = () => {
        localStorage.removeItem(STORAGE_PLAYER_ID);
        localStorage.removeItem(STORAGE_PLAYER_NAME);
        localStorage.removeItem(STORAGE_ACTIVE_ROUND);
        setPlayerId(null);
        setPlayerName('');
        setRounds([]);
        fetchPlayers();
    };

    const handleTapRound = (round) => {
        const params = new URLSearchParams();
        if (round.tee_time) params.set('tee_time', round.tee_time);
        navigate(`/play/${round.tournament_id}/${round.tee_id}?${params.toString()}`);
    };

    const getInitials = (name) => {
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    const formatTeeTime = (isoStr) => {
        if (!isoStr) return null;
        const dt = new Date(isoStr);
        return dt.toLocaleString([], {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    };

    // Check for resume state
    const activeRound = (() => {
        try {
            const raw = localStorage.getItem(STORAGE_ACTIVE_ROUND);
            return raw ? JSON.parse(raw) : null;
        } catch { return null; }
    })();

    // ===== LOADING =====
    if (loading) {
        return (
            <div className="home-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading...</span>
                </div>
            </div>
        );
    }

    // ===== PLAYER PICKER =====
    if (!playerId) {
        return (
            <div className="home-container animate-slide-up">
                <div className="home-brand-header">
                    <img src="/full-logo.jpg" alt="Golf Games Logo" className="home-logo" />
                    <h1>Golf Games</h1>
                </div>
                <div className="home-header">
                    <p>Who are you?</p>
                </div>

                {players.length === 0 ? (
                    <div className="rounds-empty">
                        <div className="rounds-empty-icon">👥</div>
                        <h3>No Players Yet</h3>
                        <p>Ask your admin to add players first.</p>
                    </div>
                ) : (
                    <div className="player-grid">
                        {players.map((p, i) => (
                            <div
                                key={p.id}
                                className="player-pick-card animate-slide-up"
                                style={{ animationDelay: `${i * 0.05}s` }}
                                onClick={() => handleSelectPlayer(p)}
                            >
                                <div className="player-avatar">{getInitials(p.name)}</div>
                                <span className="player-pick-name">{p.name}</span>
                                <span className="player-pick-hdcp">HCP {p.handicap_index}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // ===== MY ROUNDS =====
    return (
        <div className="home-container animate-slide-up">
            <div className="greeting-row">
                <div className="home-brand-header-mini">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <img src="/full-logo.jpg" alt="Golf Games Logo" className="home-logo-mini" />
                        <span className="home-brand-title">Golf Games</span>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--spacing-3)' }}>
                        <button className="change-player-link" onClick={() => navigate(`/player-stats/${playerId}`)}>
                            Stats
                        </button>
                        <button className="change-player-link" onClick={handleChangePlayer}>
                            Switch
                        </button>
                    </div>
                </div>
                <div>
                    <span className="home-subtitle">{compName}</span>
                    <h1 style={{ marginTop: 'var(--spacing-1)' }}>Hey {playerName.split(' ')[0]} 👋</h1>
                </div>
            </div>

            {/* Resume Banner — only show if round is not completed */}
            {activeRound && (() => {
                // Check if this round is actually still in progress
                const matchingRound = rounds.find(r =>
                    String(r.tee_id) === String(activeRound.teeId)
                );
                // Don't show banner if round is completed or not found
                if (!matchingRound || matchingRound.status === 'completed') {
                    // Clean up stale localStorage
                    localStorage.removeItem(STORAGE_ACTIVE_ROUND);
                    return null;
                }
                return (
                    <div
                        className="resume-banner"
                        onClick={() => {
                            const params = new URLSearchParams();
                            if (activeRound.teeTime) params.set('tee_time', activeRound.teeTime);
                            navigate(`/play/${activeRound.tournamentId}/${activeRound.teeId}?${params.toString()}`);
                        }}
                    >
                        <span className="resume-banner-text">
                            ▶ Resume your round — Hole {activeRound.currentHole || 1}
                        </span>
                        <span className="resume-banner-arrow">→</span>
                    </div>
                );
            })()}

            {rounds.length === 0 ? (
                <div className="rounds-empty">
                    <div className="rounds-empty-icon">🏌️</div>
                    <h3>No Rounds Scheduled</h3>
                    <p>Your admin hasn't set up any matches for you yet.</p>
                </div>
            ) : (
                rounds.map((round, i) => (
                    <div
                        key={round.round_id}
                        className="round-card animate-slide-up"
                        style={{ animationDelay: `${i * 0.07}s` }}
                        onClick={() => handleTapRound(round)}
                    >
                        <div className="round-card-top">
                            <div>
                                <div className="round-card-course">{round.course_name}</div>
                                <div className="round-card-tee">{round.tee_name} Tees</div>
                                {round.tee_time && (
                                    <div className="round-card-tee-time">
                                        🕐 {formatTeeTime(round.tee_time)}
                                    </div>
                                )}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.4rem' }}>
                                <span className={`round-status-badge ${round.status}`}>
                                    {round.status === 'in_progress' ? 'In Progress' : round.status}
                                </span>
                                {round.holes_completed > 0 && round.to_par !== undefined && (
                                    <span className="round-score-badge">
                                        {round.to_par === 0 ? 'E' : round.to_par > 0 ? `+${round.to_par}` : round.to_par} 
                                        <span style={{opacity: 0.7, fontWeight: 600, fontSize: '0.7rem', marginLeft: '0.2rem'}}>
                                            ({round.total_strokes})
                                        </span>
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="round-progress-bar">
                            <div
                                className="round-progress-fill"
                                style={{ width: `${(round.holes_completed / round.total_holes) * 100}%` }}
                            />
                        </div>

                        <div className="round-matchup-list">
                            {round.matchups.map(m => (
                                <div key={m.id} className="round-matchup-snippet">
                                    <span>
                                        Holes {m.hole_start}–{m.hole_end}
                                        {m.opponents.length > 0 && (
                                            <> vs {m.opponents.map(o => o.name).join(' & ')}</>
                                        )}
                                    </span>
                                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                        {m.match_result && (
                                            <span className={`matchup-result-pill ${
                                                m.match_result.startsWith('Won') || m.match_result.includes('UP') 
                                                    ? 'win' 
                                                    : m.match_result.startsWith('Lost') || m.match_result.includes('DN') 
                                                        ? 'loss' 
                                                        : 'tie'
                                            }`}>
                                                {m.match_result}
                                            </span>
                                        )}
                                        <span style={{ fontWeight: 600 }}>{m.format.replace('_', ' ')}</span>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--spacing-2)' }}>
                            <div className="round-card-play-arrow">▶</div>
                        </div>
                    </div>
                ))
            )}
        </div>
    );
}
