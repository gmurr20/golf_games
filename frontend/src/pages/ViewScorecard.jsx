import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import backend from '../api/backend';
import { Card } from '../components/ui/Card';
import './ViewScorecard.css';

export default function ViewScorecard() {
    const { tournamentId, teeId } = useParams();
    const [searchParams] = useSearchParams();
    const teeTime = searchParams.get('tee_time');
    const playerId = searchParams.get('player_id');
    const matchupId = searchParams.get('matchup_id');
    const navigate = useNavigate();
    
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchScorecard();
        const interval = setInterval(fetchScorecard, 30000);
        return () => clearInterval(interval);
    }, [tournamentId, teeId, teeTime, playerId, matchupId]);

    const fetchScorecard = async () => {
        try {
            const params = new URLSearchParams();
            if (teeTime) params.set('tee_time', teeTime);
            if (playerId) params.set('player_id', playerId);
            if (matchupId) params.set('matchup_id', matchupId);
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
            <div className="play-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading match details...</span>
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="play-container">
                <div style={{ textAlign: 'center', padding: 'var(--spacing-10)' }}>
                    <h2>Scorecard not found</h2>
                </div>
            </div>
        );
    }

    const { course_name, course_logo, tee_name, tee_time, current_hole, scorecard } = data;

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
    
    const sortedPlayerIds = Object.keys(players).sort((a, b) => {
        if (playerId && players[playerId]) {
            // Place the clicked player first
            if (a === playerId) return -1;
            if (b === playerId) return 1;

            const teamA = players[a].team;
            const teamB = players[b].team;
            const viewerTeam = players[playerId].team;

            // Place teammates of the clicked player next
            if (teamA === viewerTeam && teamB !== viewerTeam) return -1;
            if (teamB === viewerTeam && teamA !== viewerTeam) return 1;
        }
        
        // Otherwise sort by team, then alphabetically by name for a stable order
        const teamCompare = players[a].team.localeCompare(players[b].team);
        if (teamCompare !== 0) return teamCompare;
        return players[a].name.localeCompare(players[b].name);
    });

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

    const getMatchupResultClass = (text) => {
        if (!text) return '';
        if (text.includes('UP') || text.includes('Won')) return 'is-win';
        if (text.includes('DN') || text.includes('Lost') || text.includes('DOWN')) return 'is-loss';
        return 'is-neutral';
    };

    // Split holes for mobile view (Front / Back)
    const splitPoint = scorecard.length <= 9 ? scorecard.length : Math.ceil(scorecard.length / 2);
    const front9 = scorecard.filter(h => h.hole_number <= splitPoint);
    const back9 = scorecard.filter(h => h.hole_number > splitPoint);

    const renderTable = (holes, label) => {
        // Group holes by contiguous matchup_id
        const matchupGroups = [];
        let currentGroup = null;
        
        for (const h of holes) {
            if (!currentGroup || currentGroup.matchupId !== h.matchup_id) {
                currentGroup = {
                    matchupId: h.matchup_id,
                    holes: [h]
                };
                matchupGroups.push(currentGroup);
            } else {
                currentGroup.holes.push(h);
            }
        }

        return (
            <Card className="sc-table-container animate-slide-up" style={{ padding: '0', overflowX: 'auto', marginBottom: 'var(--spacing-4)' }}>
                <table className="sc-table" style={{ minWidth: '100%', margin: '0' }}>
                    <thead>
                        <tr className="sc-matchup-group-header-row">
                            <th className="sc-label">
                                <span className="sc-match-label-full">Match</span>
                                <span className="sc-label-initials">M</span>
                            </th>
                            {matchupGroups.map((g, idx) => {
                                const mInfo = data.matchups?.find(m => m.id === g.matchupId);
                                const mRes = data.match_results?.find(mr => mr.matchup_id === g.matchupId);
                                const formatText = mInfo ? mInfo.format.replace(/_/g, ' ') : (data.format ? data.format.replace(/_/g, ' ') : 'Match');
                                const resultText = mRes ? mRes.result_string : '';
                                const resultClass = getMatchupResultClass(resultText);
                                const isHeaderGroupEnd = true;
                                return (
                                    <th 
                                        key={g.matchupId || idx} 
                                        colSpan={g.holes.length}
                                        className={`sc-matchup-group-header-cell ${mRes ? 'has-results' : ''} ${isHeaderGroupEnd ? 'sc-group-end' : ''}`}
                                    >
                                        <div className="sc-matchup-group-content">
                                            <span className="sc-matchup-group-format">{formatText}</span>
                                            {resultText && (
                                                <span className={`sc-matchup-group-result ${resultClass}`}>{resultText}</span>
                                            )}
                                        </div>
                                    </th>
                                );
                            })}
                            <th className="sc-total"></th>
                        </tr>
                        <tr className="sc-header-row">
                            <th className="sc-label">{label}</th>
                            {holes.map((h, idx) => {
                                const isGroupEnd = idx === holes.length - 1 || holes[idx + 1]?.matchup_id !== h.matchup_id;
                                return (
                                    <th 
                                        key={h.hole_number} 
                                        className={isGroupEnd ? 'sc-group-end' : ''}
                                    >
                                        {h.hole_number}
                                    </th>
                                );
                            })}
                            <th className="sc-total">TOT</th>
                        </tr>
                    <tr className="sc-par-row">
                        <td className="sc-label">
                            <span className="sc-label-full">Par</span>
                            <span className="sc-label-initials">P</span>
                        </td>
                        {holes.map((h, idx) => {
                            const isGroupEnd = idx === holes.length - 1 || holes[idx + 1]?.matchup_id !== h.matchup_id;
                            return (
                                <td 
                                    key={h.hole_number} 
                                    className={isGroupEnd ? 'sc-group-end' : ''}
                                >
                                    {h.par}
                                </td>
                            );
                        })}
                        <td className="sc-total">{holes.reduce((s, h) => s + h.par, 0)}</td>
                    </tr>
                    <tr className="sc-yard-row">
                        <td className="sc-label">
                            <span className="sc-label-full">Yard</span>
                            <span className="sc-label-initials">Y</span>
                        </td>
                        {holes.map((h, idx) => {
                            const isGroupEnd = idx === holes.length - 1 || holes[idx + 1]?.matchup_id !== h.matchup_id;
                            return (
                                <td 
                                    key={h.hole_number} 
                                    className={isGroupEnd ? 'sc-group-end' : ''}
                                >
                                    {h.yardage || '–'}
                                </td>
                            );
                        })}
                        <td className="sc-total">{holes.reduce((s, h) => s + (h.yardage || 0), 0) || '–'}</td>
                    </tr>
                    {data.scoring_type === 'match_play' && (
                        <tr className="sc-match-row">
                            <td className="sc-label">
                                <span className="sc-match-label-full">Match</span>
                                <span className="sc-label-initials">M</span>
                            </td>
                            {holes.map((h, idx) => {
                                const isGroupEnd = idx === holes.length - 1 || holes[idx + 1]?.matchup_id !== h.matchup_id;
                                const mr = h.match_result;
                                if (!mr) return <td key={h.hole_number} className={isGroupEnd ? 'sc-group-end' : ''}>–</td>;
                                const display = mr.running === 0 ? 'AS' : (mr.running > 0 ? `+${mr.running}` : mr.running);
                                return (
                                    <td 
                                        key={h.hole_number} 
                                        className={`sc-match-val ${isGroupEnd ? 'sc-group-end' : ''}`}
                                    >
                                        {display}
                                    </td>
                                );
                            })}
                            <td className="sc-total"></td>
                        </tr>
                    )}
                </thead>
                <tbody>
                    {sortedPlayerIds.map(pid => {
                        let rowTotal = 0;
                        const isViewer = pid === playerId;
                        return (
                            <tr key={pid} className={`sc-player-row ${isViewer ? 'is-viewer' : ''}`}>
                                 <td className="sc-player-name">
                                    <div className="sc-player-name-text">
                                        <span className="sc-name-full">{players[pid].name}</span>
                                        <span className="sc-name-initials">{getInitials(players[pid].name)}</span>
                                    </div>
                                    <div className="sc-player-hcp-sub">
                                        Idx: {players[pid].handicap_index} • {players[pid].total_pops} strokes
                                    </div>
                                </td>
                                 {holes.map((h, idx) => {
                                     const isGroupEnd = idx === holes.length - 1 || holes[idx + 1]?.matchup_id !== h.matchup_id;
                                     const pdata = h.players[pid];
                                     const s = pdata?.score;
                                     return (
                                         <td 
                                             key={h.hole_number} 
                                             className={`${isGroupEnd ? 'sc-group-end' : ''} ${data.scoring_type === 'match_play' && pdata?.won_hole ? 'sc-hole-winner' : ''}`}
                                         >
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
            </Card>
        );
    };

    return (
        <div className="play-container animate-slide-up">
            <div className="play-top-bar">
                <button className="play-back-btn" onClick={() => navigate(-1)}>
                    ← Back
                </button>
                {data.format && data.scoring_type && (
                    <span className="match-format-badge">
                        {data.format.replace(/_/g, ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.substring(1)).join(' ')} {data.scoring_type === 'match_play' ? 'Match Play' : 'Stroke Play'} Net
                    </span>
                )}
            </div>

            <header className="hole-header" style={{ marginBottom: 'var(--spacing-6)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {course_logo ? (
                    <img src={course_logo} alt="course logo" style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '50%', marginBottom: '0.5rem', border: '2px solid var(--color-border)' }} />
                ) : (
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>⛳️</div>
                )}
                <h1 className="hole-number-label" style={{ margin: 0 }}>{course_name}</h1>
                <p style={{ color: 'var(--color-text-light)', marginTop: 'var(--spacing-1)', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                    <span>{tee_name} Tees</span>
                    {tee_time && <span>• 🕐 {formatTime(tee_time)}</span>}
                    {!data.is_completed && current_hole > 0 && current_hole < 18 && (
                        <span className="live-badge" style={{ display: 'inline-flex', verticalAlign: 'middle' }}>
                            <span className="dot"></span>
                            Live: Hole {current_hole}
                        </span>
                    )}
                </p>
            </header>

            <section className="player-par-summary animate-slide-up">
                {sortedPlayerIds.map(pid => {
                    const p = players[pid];
                    const toPar = formatToPar(p.total, p.parTotal);
                    const diff = p.total - p.parTotal;
                    const diffClass = diff < 0 ? 'under' : diff > 0 ? 'over' : 'even';
                    const isViewer = pid === playerId;

                    return (
                        <div key={pid} className={`player-par-card ${isViewer ? 'is-viewer' : ''}`}>
                            <div className="player-par-name">
                                <span className="sc-name-full">{p.name}</span>
                                <span className="sc-name-initials">{getInitials(p.name)}</span>
                            </div>
                            <div className={`player-par-score ${diffClass}`}>{toPar}</div>
                        </div>
                    );
                })}
            </section>

            {front9.length > 0 && renderTable(front9, 'OUT')}
            {back9.length > 0 && renderTable(back9, 'IN')}

            {/* Overall totals */}
            <div className="scorecard-totals-card animate-slide-up" style={{ marginTop: 'var(--spacing-6)' }}>
                <table className="golf-scorecard-table">
                    <thead>
                        <tr>
                            <th className="sc-label-cell"></th>
                            <th className="sc-total-header">OUT</th>
                            <th className="sc-total-header">IN</th>
                            <th className="sc-total-header">TOT</th>
                            <th className="sc-total-header">+/–</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedPlayerIds.map(pid => {
                            const p = players[pid];
                            const isHighlighted = pid === playerId;

                            let outTotal = 0;
                            let outPar = 0;
                            let hasOut = false;
                            front9.forEach(h => {
                                const s = h.players[pid]?.score;
                                if (s != null) {
                                    outTotal += s;
                                    outPar += h.par;
                                    hasOut = true;
                                }
                            });

                            let inTotal = 0;
                            let inPar = 0;
                            let hasIn = false;
                            back9.forEach(h => {
                                const s = h.players[pid]?.score;
                                if (s != null) {
                                    inTotal += s;
                                    inPar += h.par;
                                    hasIn = true;
                                }
                            });

                            const grandTotal = (hasOut ? outTotal : 0) + (hasIn ? inTotal : 0);
                            const totalPar = (hasOut ? outPar : 0) + (hasIn ? inPar : 0);
                            const diff = grandTotal - totalPar;
                            const diffStr = diff === 0 ? 'E' : (diff > 0 ? `+${diff}` : `${diff}`);

                            return (
                                <tr key={pid} className={isHighlighted ? 'sc-me-row' : ''}>
                                    <td className="sc-player-name" style={{ position: 'sticky', left: 0, zIndex: 10, background: 'var(--color-surface)' }}>
                                        <span className="sc-name-full">{p.name} <span className="sc-player-hcp">({p.total_pops || 0})</span></span>
                                        <span className="sc-name-initials">{getInitials(p.name)} <span className="sc-player-hcp">({p.total_pops || 0})</span></span>
                                        {isHighlighted && <span className="sc-you-dot"></span>}
                                    </td>
                                    <td className="sc-total-cell">{hasOut ? outTotal : '–'}</td>
                                    <td className="sc-total-cell">{hasIn ? inTotal : '–'}</td>
                                    <td className="sc-total-cell" style={{ fontWeight: 700 }}>{(hasOut || hasIn) ? grandTotal : '–'}</td>
                                    <td className={`sc-total-cell ${(hasOut || hasIn) && diff < 0 ? 'sc-under' : (hasOut || hasIn) && diff > 0 ? 'sc-over' : ''}`}>
                                        {(hasOut || hasIn) ? diffStr : '–'}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
