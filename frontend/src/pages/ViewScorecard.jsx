import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import './ViewScorecard.css';

export default function ViewScorecard() {
    const { tournamentId, teeId } = useParams();
    const [searchParams] = useSearchParams();
    const teeTime = searchParams.get('tee_time');
    const playerId = searchParams.get('player_id');
    const navigate = useNavigate();
    
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchScorecard();
        const interval = setInterval(fetchScorecard, 30000);
        return () => clearInterval(interval);
    }, [tournamentId, teeId, teeTime, playerId]);

    const fetchScorecard = async () => {
        try {
            const params = new URLSearchParams();
            if (teeTime) params.set('tee_time', teeTime);
            if (playerId) params.set('player_id', playerId);
            const res = await backend.get(`/scorecard/${tournamentId}/${teeId}?${params.toString()}`);
            setData(res.data);
        } catch (e) {
            console.error('Failed to fetch scorecard', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <div className="view-scorecard-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading match details...</span>
                </div>
            </div>
        );
    }

    if (!data) return <div className="view-scorecard-container">Scorecard not found.</div>;

    const { course_name, tee_name, tee_time, current_hole, scorecard } = data;

    // Use player_totals directly from the backend
    const playerTotals = data.player_totals || {};
    
    // Extract metadata from the first hole's player data
    const players = {};
    if (scorecard.length > 0) {
        Object.entries(scorecard[0].players).forEach(([pid, pdata]) => {
            const pt = playerTotals[pid] || {};
            players[pid] = {
                name: pdata.name,
                team: pdata.team,
                total: pt.total_raw || 0,
                parTotal: pt.total_par || 0,
                holesPlayed: pt.holes_played || 0,
                handicap_index: pdata.handicap_index,
                total_pops: pdata.total_pops,
                netTotal: pt.total_net || 0
            };
        });
    }
    
    const sortedPlayerIds = Object.keys(players).sort((a,b) => players[a].team.localeCompare(players[b].team));

    const formatToPar = (score, par) => {
        const diff = score - par;
        if (diff === 0) return 'E';
        return diff > 0 ? `+${diff}` : diff;
    };

    const getInitials = (name) => {
        if (!name) return '';
        return name.split(' ').map(part => part[0]).join('').toUpperCase();
    };

    const getScoreClass = (score, par) => {
        if (!score) return '';
        const diff = score - par;
        if (diff <= -2) return 'eagle';
        if (diff === -1) return 'birdie';
        if (diff === 1) return 'bogey';
        if (diff >= 2) return 'dbl-bogey';
        return '';
    };

    const formatTime = (iso) => {
        if (!iso) return '';
        return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    };

    // Split holes for mobile view (Front 9 / Back 9)
    const front9 = scorecard.filter(h => h.hole_number <= 9);
    const back9 = scorecard.filter(h => h.hole_number > 9);

    const renderTable = (holes, label) => (
        <div className="sc-table-container animate-slide-up" style={{ marginBottom: 'var(--spacing-4)' }}>
            <table className="sc-table">
                <thead>
                    <tr className="sc-header-row">
                        <th className="sc-label">{label}</th>
                        {holes.map(h => (
                            <th key={h.hole_number}>{h.hole_number}</th>
                        ))}
                        <th className="sc-total">TOT</th>
                    </tr>
                    <tr className="sc-par-row">
                        <td className="sc-label">
                            <span className="sc-label-full">Par</span>
                        </td>
                        {holes.map(h => (
                            <td key={h.hole_number}>{h.par}</td>
                        ))}
                        <td className="sc-total">{holes.reduce((s, h) => s + h.par, 0)}</td>
                    </tr>
                    {data.scoring_type === 'match_play' && (
                        <tr className="sc-match-row">
                            <td className="sc-label">
                                <span className="sc-match-label-full">Match</span>
                            </td>
                            {holes.map(h => {
                                const mr = h.match_result;
                                if (!mr) return <td key={h.hole_number}>–</td>;
                                const display = mr.running === 0 ? 'AS' : (mr.running > 0 ? `+${mr.running}` : mr.running);
                                return <td key={h.hole_number} className="sc-match-val">{display}</td>;
                            })}
                            <td className="sc-total"></td>
                        </tr>
                    )}
                </thead>
                <tbody>
                    {sortedPlayerIds.map(pid => {
                        let rowTotal = 0;
                        return (
                            <tr key={pid} className="sc-player-row">
                                 <td className="sc-player-name">
                                    <div className="sc-player-name-text">
                                        <span className="sc-name-full">{players[pid].name}</span>
                                        <span className="sc-name-initials">{getInitials(players[pid].name)}</span>
                                    </div>
                                    <div className="sc-player-hcp-sub">
                                        Idx: {players[pid].handicap_index} • {players[pid].total_pops} strokes
                                    </div>
                                </td>
                                {holes.map(h => {
                                    const pdata = h.players[pid];
                                    const s = pdata?.score;
                                    return (
                                        <td key={h.hole_number}>
                                            <span className={`sc-score-val ${getScoreClass(s, h.par)}`}>
                                                {s || '–'}
                                            </span>
                                            {pdata?.pops !== 0 && (
                                                <span className={`sc-pop-dot ${pdata.pops < 0 ? 'sc-pop-plus' : ''}`}>
                                                    {pdata.pops > 0 ? '●'.repeat(pdata.pops) : '○'.repeat(Math.abs(pdata.pops))}
                                                </span>
                                            )}
                                        </td>
                                    );
                                })}
                                <td className="sc-total">{holes.reduce((sum, h) => sum + (h.players[pid]?.score || 0), 0) || '–'}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );

    return (
        <div className="view-scorecard-container">
            <div className="back-link" onClick={() => navigate(-1)} style={{ cursor: 'pointer' }}>
                ← Back
            </div>

            <header className="view-scorecard-header">
                <h1>{course_name}</h1>
                <div className="view-scorecard-meta">
                    <span>{tee_name} Tees</span>
                    {tee_time && <span>🕐 {formatTime(tee_time)}</span>}
                    {current_hole > 0 && current_hole < 18 && (
                        <span className="live-badge">
                            <span className="dot"></span>
                            Live: Hole {current_hole}
                        </span>
                    )}
                    {data.format && data.scoring_type && (
                        <span className="match-format-badge">
                            {data.format.charAt(0).toUpperCase() + data.format.slice(1)} {data.scoring_type === 'match_play' ? 'Match Play' : 'Stroke Play'} Net
                        </span>
                    )}
                </div>
            </header>

            <section className="player-par-summary animate-slide-up">
                {sortedPlayerIds.map(pid => {
                    const p = players[pid];
                    const toPar = formatToPar(p.total, p.parTotal);
                    const diff = p.total - p.parTotal;
                    const diffClass = diff < 0 ? 'under' : diff > 0 ? 'over' : 'even';

                    return (
                        <div key={pid} className="player-par-card">
                            <div className="player-par-name">
                                <span className="sc-name-full">{p.name}</span>
                                <span className="sc-name-initials">{getInitials(p.name)}</span>
                            </div>
                            <div className={`player-par-score ${diffClass}`}>{toPar}</div>
                        </div>
                    );
                })}
            </section>



            {renderTable(front9, 'OUT')}
            {renderTable(back9, 'IN')}
        </div>
    );
}
