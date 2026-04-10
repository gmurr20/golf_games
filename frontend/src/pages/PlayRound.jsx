import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import backend from '../api/backend';
import './PlayRound.css';

const STORAGE_ACTIVE_ROUND = 'golf_active_round';
const STORAGE_PLAYER_ID = 'golf_player_id';

export default function PlayRound() {
    const { tournamentId, teeId } = useParams();
    const [searchParams] = useSearchParams();
    const teeTime = searchParams.get('tee_time');
    const navigate = useNavigate();

    const [scorecard, setScorecard] = useState(null);
    const [loading, setLoading] = useState(true);
    const [currentHole, setCurrentHole] = useState(1);
    const [scores, setScores] = useState({}); // { holeNumber: { playerId: strokes } }
    const [saving, setSaving] = useState(false);
    const [complete, setComplete] = useState(false);
    const [viewingScorecard, setViewingScorecard] = useState(false);
    const [editing, setEditing] = useState(false); // user tapped "Edit Scores" from scorecard
    const [matchResults, setMatchResults] = useState([]);
    const playerId = parseInt(localStorage.getItem(STORAGE_PLAYER_ID));
    const saveTimeoutRef = useRef(null);

    // Fetch scorecard on mount
    useEffect(() => {
        fetchScorecard();
    }, []);

    const fetchScorecard = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (teeTime) params.set('tee_time', teeTime);
            const res = await backend.get(
                `/players/${playerId}/round/${tournamentId}/${teeId}/scorecard?${params.toString()}`
            );
            const data = res.data;
            setScorecard(data);

            // Hydrate scores from backend data
            const existingScores = {};
            let latestHoleWithScore = 0;
            for (const hole of data.scorecard) {
                existingScores[hole.hole_number] = {};
                for (const [pid, pdata] of Object.entries(hole.players)) {
                    if (pdata.score !== null && pdata.score !== undefined) {
                        existingScores[hole.hole_number][pid] = pdata.score;
                        if (hole.hole_number > latestHoleWithScore) {
                            latestHoleWithScore = hole.hole_number;
                        }
                    }
                }
            }

            // Check localStorage for draft scores and merge
            try {
                const stored = JSON.parse(localStorage.getItem(STORAGE_ACTIVE_ROUND));
                if (stored && String(stored.tournamentId) === tournamentId &&
                    String(stored.teeId) === teeId) {
                    if (stored.draftScores) {
                        for (const [holeNum, playerScores] of Object.entries(stored.draftScores)) {
                            if (!existingScores[holeNum]) existingScores[holeNum] = {};
                            for (const [pid, strokes] of Object.entries(playerScores)) {
                                if (existingScores[holeNum][pid] === undefined) {
                                    existingScores[holeNum][pid] = strokes;
                                }
                            }
                        }
                    }
                    if (stored.currentHole) {
                        latestHoleWithScore = Math.max(latestHoleWithScore, stored.currentHole - 1);
                    }
                }
            } catch { }

            setScores(existingScores);

            // Determine starting hole
            const totalHoles = data.scorecard.length;
            const allComplete = data.scorecard.every(h => {
                const myScore = existingScores[h.hole_number]?.[String(playerId)];
                return myScore !== undefined && myScore !== null;
            });

            if (allComplete) {
                setComplete(true);
                // Clear the active round from localStorage so resume banner disappears
                localStorage.removeItem(STORAGE_ACTIVE_ROUND);
                setCurrentHole(data.scorecard[totalHoles - 1].hole_number);
            } else {
                let startHole = data.scorecard[0].hole_number;
                for (const h of data.scorecard) {
                    const myScore = existingScores[h.hole_number]?.[String(playerId)];
                    if (myScore === undefined || myScore === null) {
                        startHole = h.hole_number;
                        break;
                    }
                }
                setCurrentHole(startHole);
            }
        } catch (e) {
            console.error('Failed to fetch scorecard', e);
        } finally {
            setLoading(false);
        }
    };

    // Persist state to localStorage — only when NOT complete
    useEffect(() => {
        if (!scorecard || complete) return;
        const state = {
            tournamentId,
            teeId,
            teeTime,
            currentHole,
            draftScores: scores,
        };
        localStorage.setItem(STORAGE_ACTIVE_ROUND, JSON.stringify(state));
    }, [scores, currentHole, scorecard, complete]);

    const getHoleData = useCallback((holeNum) => {
        if (!scorecard) return null;
        return scorecard.scorecard.find(h => h.hole_number === holeNum);
    }, [scorecard]);

    const currentHoleData = getHoleData(currentHole);

    const getScore = (holeNum, pid) => {
        return scores[holeNum]?.[String(pid)];
    };

    const setPlayerScore = (holeNum, pid, value) => {
        setScores(prev => ({
            ...prev,
            [holeNum]: {
                ...prev[holeNum],
                [String(pid)]: value === undefined ? undefined : Math.max(1, value),
            }
        }));
    };

    const defaultScoreForHole = (holeData) => {
        return holeData?.par || 4;
    };

    // Save scores for current hole and advance
    const handleSaveAndNext = async () => {
        if (!currentHoleData) return;
        setSaving(true);

        const batchScores = [];
        const playerEntries = Object.entries(currentHoleData.players);

        for (const [pid, pdata] of playerEntries) {
            const rawScore = getScore(currentHole, pid);
            const strokes = rawScore !== undefined ? rawScore : defaultScoreForHole(currentHoleData);
            setPlayerScore(currentHole, pid, strokes);

            batchScores.push({
                matchup_id: currentHoleData.matchup_id,
                player_id: parseInt(pid),
                hole_number: currentHole,
                strokes: strokes,
            });
        }

        try {
            await backend.post('/scores/batch', batchScores);
        } catch (e) {
            console.error('Failed to save scores', e);
        }

        if (scorecard) {
            const holes = scorecard.scorecard;
            const currentIdx = holes.findIndex(h => h.hole_number === currentHole);
            if (currentIdx < holes.length - 1) {
                setCurrentHole(holes[currentIdx + 1].hole_number);
            } else {
                setComplete(true);
                localStorage.removeItem(STORAGE_ACTIVE_ROUND);
            }
        }

        setSaving(false);
    };

    // Save a single hole (used when editing from scorecard)
    const handleSaveCurrentHole = async () => {
        if (!currentHoleData) return;
        setSaving(true);

        const batchScores = [];
        for (const [pid, pdata] of Object.entries(currentHoleData.players)) {
            const rawScore = getScore(currentHole, pid);
            const strokes = rawScore !== undefined ? rawScore : defaultScoreForHole(currentHoleData);
            setPlayerScore(currentHole, pid, strokes);
            batchScores.push({
                matchup_id: currentHoleData.matchup_id,
                player_id: parseInt(pid),
                hole_number: currentHole,
                strokes: strokes,
            });
        }

        try {
            await backend.post('/scores/batch', batchScores);
        } catch (e) {
            console.error('Failed to save scores', e);
        }

        setSaving(false);
        setEditing(false);
        
        // Check if all holes are actually complete before forcing complete
        const allHolesScored = scorecard.scorecard.every(h => 
            h.hole_number === currentHole ? true : (getScore(h.hole_number, String(playerId)) != null)
        );
        if (allHolesScored) {
            setComplete(true);
        } else {
            setComplete(false);
        }
    };

    const handleClearHoleScores = async () => {
        if (!currentHoleData) return;
        if (!window.confirm('Are you sure you want to delete all scores for this hole?')) return;
        
        setSaving(true);
        const batchScores = [];
        for (const pid of Object.keys(currentHoleData.players)) {
            setPlayerScore(currentHole, pid, undefined);
            batchScores.push({
                matchup_id: currentHoleData.matchup_id,
                player_id: parseInt(pid),
                hole_number: currentHole,
                strokes: null,
            });
        }

        try {
            await backend.post('/scores/batch', batchScores);
        } catch (e) {
            console.error('Failed to clear scores', e);
        }

        setSaving(false);
        setEditing(false);
        setComplete(false); // Kick back to "in progress"
    };

    const isHoleComplete = (holeNum) => {
        return getScore(holeNum, String(playerId)) != null;
    };

    // Compute match status for display — scoped to current competition only
    const getMatchStatusDisplay = () => {
        if (!scorecard || !currentHoleData) return { text: '', className: 'status-even' };

        const currentMatchupId = currentHoleData.matchup_id;

        let myWins = 0, oppWins = 0;
        for (const h of scorecard.scorecard) {
            // Only count holes in the same competition (matchup)
            if (h.matchup_id !== currentMatchupId) continue;
            if (h.hole_number >= currentHole) break;
            const players = Object.entries(h.players);
            const myTeam = scorecard.my_team;

            let bestMy = Infinity, bestOpp = Infinity;
            for (const [pid, pdata] of players) {
                const raw = getScore(h.hole_number, pid);
                if (raw == null) continue;
                const net = raw - (pdata.pops || 0);
                if (pdata.team === myTeam) {
                    bestMy = Math.min(bestMy, net);
                } else {
                    bestOpp = Math.min(bestOpp, net);
                }
            }

            if (bestMy < Infinity && bestOpp < Infinity) {
                if (bestMy < bestOpp) myWins++;
                else if (bestOpp < bestMy) oppWins++;
            }
        }

        const diff = myWins - oppWins;
        if (diff === 0) return { text: `All Square`, className: 'status-even' };
        if (diff > 0) return { text: `${diff} UP`, className: 'status-up' };
        return { text: `${Math.abs(diff)} DOWN`, className: 'status-down' };
    };

    // Get golf-style CSS class for a score relative to par
    const getScoreClass = (strokes, par) => {
        if (strokes == null) return '';
        const diff = strokes - par;
        if (diff <= -2) return 'score-eagle';
        if (diff === -1) return 'score-birdie';
        if (diff === 0) return 'score-par';
        if (diff === 1) return 'score-bogey';
        return 'score-dbl-bogey'; // +2 or worse
    };

    // Get total score for a player
    const getPlayerTotal = (pid) => {
        let total = 0;
        let count = 0;
        for (const h of scorecard.scorecard) {
            const s = getScore(h.hole_number, pid);
            if (s != null) {
                total += s;
                count++;
            }
        }
        return { total, count };
    };

    // Get total par
    const getTotalPar = () => {
        return scorecard.scorecard.reduce((sum, h) => sum + h.par, 0);
    };

    // ===== LOADING =====
    if (loading || !scorecard) {
        return (
            <div className="play-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading scorecard...</span>
                </div>
            </div>
        );
    }

    // ===== COMPLETED ROUND — GOLF SCORECARD =====
    if ((complete || viewingScorecard) && !editing) {
        const totalPar = getTotalPar();
        // Get all unique player IDs across the scorecard
        const allPlayerIds = [...new Set(
            scorecard.scorecard.flatMap(h => Object.keys(h.players))
        )];
        // Sort: me first, then teammates, then opponents
        allPlayerIds.sort((a, b) => {
            const aData = scorecard.scorecard[0]?.players[a];
            const bData = scorecard.scorecard[0]?.players[b];
            if (!aData || !bData) return 0;
            if (aData.is_me) return -1;
            if (bData.is_me) return 1;
            if (aData.team === scorecard.my_team && bData.team !== scorecard.my_team) return -1;
            if (bData.team === scorecard.my_team && aData.team !== scorecard.my_team) return 1;
            return 0;
        });

        // Split holes into front 9 / back 9
        const front9 = scorecard.scorecard.filter(h => h.hole_number <= 9);
        const back9 = scorecard.scorecard.filter(h => h.hole_number > 9);

        const renderScorecardTable = (holes, label) => {
            if (holes.length === 0) return null;
            return (
                <div className="scorecard-table-wrapper">
                    <table className="golf-scorecard-table">
                        <thead>
                            <tr>
                                <th className="sc-label-cell">{label}</th>
                                {holes.map(h => (
                                    <th key={h.hole_number} className="sc-hole-header">{h.hole_number}</th>
                                ))}
                                <th className="sc-total-header">TOT</th>
                            </tr>
                            <tr className="sc-par-row">
                                <td className="sc-label-cell">Par</td>
                                {holes.map(h => (
                                    <td key={h.hole_number} className="sc-par-cell">{h.par}</td>
                                ))}
                                <td className="sc-par-cell sc-total-cell">
                                    {holes.reduce((s, h) => s + h.par, 0)}
                                </td>
                            </tr>
                            {holes.some(h => h.match_result) && (
                                <tr className="sc-match-row">
                                    <td className="sc-label-cell">Match</td>
                                    {holes.map(h => {
                                        const mr = h.match_result;
                                        let display = '–';
                                        let className = '';
                                        if (mr) {
                                            if (mr.running === 0) display = 'AS';
                                            else if (mr.running > 0) display = `+${mr.running}`;
                                            else display = `${mr.running}`;
                                            
                                            if (mr.result === 'won') className = 'sc-match-won';
                                            else if (mr.result === 'lost') className = 'sc-match-lost';
                                            else if (mr.result === 'halved') className = 'sc-match-halved';
                                        }
                                        return <td key={h.hole_number} className={`sc-match-cell ${className}`}>{display}</td>
                                    })}
                                    <td className="sc-match-cell"></td>
                                </tr>
                            )}
                        </thead>
                        <tbody>
                            {allPlayerIds.map(pid => {
                                const firstHoleData = holes[0]?.players[pid];
                                const name = firstHoleData?.name || 'Unknown';
                                const isMe = firstHoleData?.is_me;
                                let sectionTotal = 0;
                                let sectionCount = 0;

                                return (
                                    <tr key={pid} className={isMe ? 'sc-me-row' : ''}>
                                        <td className="sc-player-name">
                                            {name}
                                            {isMe && <span className="sc-you-dot"></span>}
                                        </td>
                                        {holes.map(h => {
                                            const s = getScore(h.hole_number, pid);
                                            const pdata = h.players[pid];
                                            if (s != null) {
                                                sectionTotal += s;
                                                sectionCount++;
                                            }
                                            return (
                                                <td
                                                    key={h.hole_number}
                                                    className="sc-score-cell"
                                                    onClick={() => {
                                                        setCurrentHole(h.hole_number);
                                                        setEditing(!complete);
                                                        setViewingScorecard(false);
                                                        setComplete(false);
                                                    }}
                                                >
                                                    {s != null ? (
                                                        <span className={`sc-score-mark ${getScoreClass(s, h.par)}`}>
                                                            {s}
                                                        </span>
                                                    ) : (
                                                        <span className="sc-score-empty">–</span>
                                                    )}
                                                    {pdata?.pops > 0 && (
                                                        <span className="sc-pop-dot">{'●'.repeat(pdata.pops)}</span>
                                                    )}
                                                </td>
                                            );
                                        })}
                                        <td className="sc-total-cell">
                                            {sectionCount > 0 ? sectionTotal : '–'}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            );
        };

        return (
            <div className="play-container">
                <div className="play-top-bar">
                    <button className="play-back-btn" onClick={() => navigate(-1)}>
                        ← Back
                    </button>
                    <span className="play-course-label">
                        {scorecard.course_name} · {scorecard.tee_name}
                    </span>
                </div>

                <div className="scorecard-complete-header animate-slide-up">
                    <div className="round-complete-trophy">{complete ? '🏆' : '⛳️'}</div>
                    <h2>{complete ? 'Round Complete' : 'Live Scorecard'}</h2>
                    <p className="round-complete-subtitle">
                        {scorecard.course_name} — {scorecard.tee_name} Tees
                    </p>
                    {/* Total score summary */}
                    {(() => {
                        const { total, count } = getPlayerTotal(String(playerId));
                        let playedPar = 0;
                        scorecard.scorecard.forEach(h => {
                            if (getScore(h.hole_number, String(playerId)) != null) {
                                playedPar += h.par;
                            }
                        });
                        const diff = total - playedPar;
                        const diffStr = diff === 0 ? 'E' : (diff > 0 ? `+${diff}` : `${diff}`);
                        return count > 0 ? (
                            <div className="total-score-display">
                                <span className="total-score-number">{total}</span>
                                <span className={`total-score-diff ${diff < 0 ? 'under' : diff > 0 ? 'over' : 'even'}`}>
                                    ({diffStr})
                                </span>
                            </div>
                        ) : null;
                    })()}
                </div>

                {/* Golf-style scorecard legend */}
                <div className="sc-legend animate-slide-up" style={{ animationDelay: '0.1s' }}>
                    <span className="sc-legend-item"><span className="sc-score-mark score-eagle">2</span> Eagle</span>
                    <span className="sc-legend-item"><span className="sc-score-mark score-birdie">3</span> Birdie</span>
                    <span className="sc-legend-item"><span className="sc-score-mark score-par">4</span> Par</span>
                    <span className="sc-legend-item"><span className="sc-score-mark score-bogey">5</span> Bogey</span>
                    <span className="sc-legend-item"><span className="sc-score-mark score-dbl-bogey">6</span> Dbl Bogey+</span>
                </div>

                {/* Scorecard tables */}
                <div className="animate-slide-up" style={{ animationDelay: '0.15s' }}>
                    {renderScorecardTable(front9, 'OUT')}
                    {renderScorecardTable(back9, 'IN')}
                </div>

                {/* Overall totals */}
                <div className="scorecard-totals-card animate-slide-up" style={{ animationDelay: '0.2s' }}>
                    <table className="golf-scorecard-table">
                        <thead>
                            <tr>
                                <th className="sc-label-cell">Total</th>
                                <th className="sc-total-header">OUT</th>
                                <th className="sc-total-header">IN</th>
                                <th className="sc-total-header">TOT</th>
                                <th className="sc-total-header">+/–</th>
                            </tr>
                        </thead>
                        <tbody>
                            {allPlayerIds.map(pid => {
                                const firstHoleData = scorecard.scorecard[0]?.players[pid];
                                const name = firstHoleData?.name || 'Unknown';
                                const isMe = firstHoleData?.is_me;

                                let outTotal = 0, inTotal = 0;
                                let playedPar = 0;
                                front9.forEach(h => { const s = getScore(h.hole_number, pid); if (s != null) { outTotal += s; playedPar += h.par; } });
                                back9.forEach(h => { const s = getScore(h.hole_number, pid); if (s != null) { inTotal += s; playedPar += h.par; } });
                                const grandTotal = outTotal + inTotal;
                                const diff = grandTotal - playedPar;
                                const diffStr = diff === 0 ? 'E' : (diff > 0 ? `+${diff}` : `${diff}`);

                                return (
                                    <tr key={pid} className={isMe ? 'sc-me-row' : ''}>
                                        <td className="sc-player-name">
                                            {name}
                                            {isMe && <span className="sc-you-dot"></span>}
                                        </td>
                                        <td className="sc-total-cell">{outTotal || '–'}</td>
                                        <td className="sc-total-cell">{inTotal || '–'}</td>
                                        <td className="sc-total-cell" style={{ fontWeight: 700 }}>{grandTotal || '–'}</td>
                                        <td className={`sc-total-cell ${diff < 0 ? 'sc-under' : diff > 0 ? 'sc-over' : ''}`}>
                                            {grandTotal ? diffStr : '–'}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                <div className="scorecard-actions animate-slide-up" style={{ animationDelay: '0.25s' }}>
                    <button
                        className="edit-scores-btn"
                        onClick={() => {
                            setViewingScorecard(false);
                            if (complete) {
                                setEditing(true);
                                setComplete(false);
                                setCurrentHole(scorecard.scorecard[0].hole_number);
                            }
                        }}
                    >
                        {complete ? '✏️ Edit Scores' : '← Back to Active Hole'}
                    </button>
                    {complete && <p className="sc-edit-hint">Tap any score cell above to jump to that hole</p>}
                </div>
            </div>
        );
    }

    // ===== HOLE-BY-HOLE SCORING (also used for editing) =====
    const matchStatus = getMatchStatusDisplay();
    const isEditMode = editing;

    const sortedPlayers = currentHoleData
        ? Object.entries(currentHoleData.players).sort(([, a], [, b]) => {
            if (a.is_me) return -1;
            if (b.is_me) return 1;
            if (a.team === scorecard.my_team && b.team !== scorecard.my_team) return -1;
            if (b.team === scorecard.my_team && a.team !== scorecard.my_team) return 1;
            return 0;
        })
        : [];

    return (
        <div className="play-container">
            {/* Top bar */}
            <div className="play-top-bar">
                <button className="play-back-btn" onClick={() => {
                    if (isEditMode) {
                        setEditing(false);
                        setComplete(true);
                    } else if (viewingScorecard) {
                        setViewingScorecard(false);
                    } else {
                        navigate(-1);
                    }
                }}>
                    ← {isEditMode || viewingScorecard ? 'Scorecard' : 'Back'}
                </button>
                <span className="play-course-label">
                    {scorecard.course_name} · {scorecard.tee_name}
                </span>
            </div>

            {isEditMode && (
                <div className="edit-mode-banner">
                    ✏️ Editing — tap Save when done
                </div>
            )}

            {/* Hole header */}
            <div className="hole-header animate-slide-up" key={`header-${currentHole}`}>
                <div className="hole-header-top">
                    {(() => {
                        const idx = scorecard.scorecard.findIndex(h => h.hole_number === currentHole);
                        const prevHole = idx > 0 ? scorecard.scorecard[idx - 1].hole_number : null;
                        const nextHole = idx < scorecard.scorecard.length - 1 ? scorecard.scorecard[idx + 1].hole_number : null;
                        
                        return (
                            <>
                                {prevHole != null ? (
                                    <button className="hole-nav-arrow" onClick={() => setCurrentHole(prevHole)}>
                                        &lsaquo;
                                    </button>
                                ) : <div className="hole-nav-arrow-placeholder" />}
                                
                                <h1 className="hole-number-label">Hole {currentHole}</h1>
                                
                                {nextHole != null ? (
                                    <button className="hole-nav-arrow" onClick={() => setCurrentHole(nextHole)}>
                                        &rsaquo;
                                    </button>
                                ) : <div className="hole-nav-arrow-placeholder" />}
                            </>
                        );
                    })()}
                </div>
                <div className="hole-info-row">
                    <span className="hole-info-chip">Par {currentHoleData?.par}</span>
                    {currentHoleData?.yardage && (
                        <span className="hole-info-chip">{currentHoleData.yardage} yds</span>
                    )}
                    <span className="hole-info-chip">HDCP {currentHoleData?.handicap_index}</span>
                </div>
            </div>

            {/* Match status — scoped to current competition */}
            {!isEditMode && (() => {
                const currentMatchupId = currentHoleData?.matchup_id;
                const firstHoleInMatchup = scorecard.scorecard.find(h => h.matchup_id === currentMatchupId);
                return currentHole > (firstHoleInMatchup?.hole_number || 1);
            })() && (
                <div style={{ textAlign: 'center', marginBottom: 'var(--spacing-3)' }}>
                    <span className={`match-status-ticker ${matchStatus.className}`}>
                        {matchStatus.text}
                    </span>
                </div>
            )}

            {/* Score entries */}
            <div className="score-entries" key={`scores-${currentHole}`}>
                {sortedPlayers.map(([pid, pdata], idx) => {
                    const rawScore = getScore(currentHole, pid);
                    const currentScore = rawScore ?? defaultScoreForHole(currentHoleData);
                    
                    const par = currentHoleData?.par || 4;
                    const scoreClass = currentScore < par ? 'under-par'
                        : currentScore > par ? 'over-par'
                        : 'at-par';

                    return (
                        <div
                            key={pid}
                            className={`score-entry-card ${pdata.is_me ? 'is-me' : ''} animate-slide-up`}
                            style={{ animationDelay: `${idx * 0.06}s` }}
                        >
                            <div className="score-entry-label">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span className="score-entry-name">{pdata.name}</span>
                                    {pdata.pops > 0 && (
                                        <span className="stroke-dots" title={`${pdata.pops} stroke${pdata.pops > 1 ? 's' : ''} on this hole`}>
                                            {'●'.repeat(pdata.pops)}
                                        </span>
                                    )}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    {pdata.pops > 0 && (
                                        <span className="stroke-badge">
                                            {pdata.pops > 1 ? `${pdata.pops} strokes` : '1 stroke'}
                                        </span>
                                    )}
                                    {pdata.is_me && <span className="score-entry-you-badge">You</span>}
                                </div>
                            </div>
                            <div className="score-stepper">
                                <button
                                    className="stepper-btn"
                                    type="button"
                                    onClick={() => setPlayerScore(currentHole, pid, currentScore <= 1 ? undefined : currentScore - 1)}
                                >
                                    −
                                </button>
                                <span className={`stepper-value ${scoreClass}`}>
                                    {currentScore}
                                </span>
                                <button
                                    className="stepper-btn"
                                    type="button"
                                    onClick={() => setPlayerScore(currentHole, pid, currentScore + 1)}
                                >
                                    +
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Save & Next */}
            <div className="play-bottom-actions">
                {isEditMode ? (
                    <button
                        className="save-next-btn"
                        onClick={handleSaveCurrentHole}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : '✓ Save & Back to Scorecard'}
                    </button>
                ) : (
                    <button
                        className="save-next-btn"
                        onClick={handleSaveAndNext}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : (
                            scorecard.scorecard.findIndex(h => h.hole_number === currentHole) === scorecard.scorecard.length - 1
                                ? '✓ Finish Round'
                                : 'Save & Next →'
                        )}
                    </button>
                )}
                
                {/* Clear hole scores */}
                <button
                    className="clear-hole-scores-btn"
                    onClick={handleClearHoleScores}
                    disabled={saving}
                >
                    Delete Hole Scores
                </button>

                {!complete && (
                    <button
                        className="view-scorecard-btn"
                        onClick={() => setViewingScorecard(true)}
                        style={{marginTop: 'var(--spacing-2)', width: '100%', padding: 'var(--spacing-3)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', fontWeight: 600, color: 'var(--color-text)'}}
                    >
                        📊 View Full Scorecard
                    </button>
                )}

                <div className={`saving-indicator ${saving ? 'visible' : 'hidden'}`}>
                    Syncing with server...
                </div>
            </div>

            {/* Hole navigation dots */}
            <div className="hole-nav-dots">
                {scorecard.scorecard.map(h => (
                    <button
                        key={h.hole_number}
                        className={`hole-dot ${h.hole_number === currentHole ? 'active' : ''} ${isHoleComplete(h.hole_number) ? 'completed' : ''}`}
                        onClick={() => setCurrentHole(h.hole_number)}
                    >
                        {h.hole_number}
                    </button>
                ))}
            </div>
        </div>
    );
}
