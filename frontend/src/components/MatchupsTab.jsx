import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import backend from '../api/backend';
import './MatchupsTab.css';

export default function MatchupsTab({
    courses, players, matchups, fetchMatchups, setStatus,
    teamAName, teamBName
}) {
    // Create Form State
    const navigate = useNavigate();
    const [mFormat, setMFormat] = useState('match_play');
    const [useHandicaps, setUseHandicaps] = useState(true);
    const [mTeeId, setMTeeId] = useState('');
    const [teamA1, setTeamA1] = useState('');
    const [teamA2, setTeamA2] = useState('');
    const [teamB1, setTeamB1] = useState('');
    const [teamB2, setTeamB2] = useState('');
    const [pointsWin, setPointsWin] = useState('1');
    const [pointsPush, setPointsPush] = useState('0.5');
    const [selectedRanges, setSelectedRanges] = useState([{ start: 1, end: 18 }]);
    const [customStart, setCustomStart] = useState('1');
    const [customEnd, setCustomEnd] = useState('18');
    const [teeTime, setTeeTime] = useState('');
    const [showCreate, setShowCreate] = useState(false);

    const arrTeamA = players.filter(p => p.team === teamAName);
    const arrTeamB = players.filter(p => p.team === teamBName);
    const arrUnassigned = players.filter(p => p.team !== teamAName && p.team !== teamBName);

    const resetForm = () => {
        setMFormat('match_play');
        setUseHandicaps(true);
        setMTeeId('');
        setTeamA1(''); setTeamA2('');
        setTeamB1(''); setTeamB2('');
        setPointsWin('1'); setPointsPush('0.5');
        setSelectedRanges([{ start: 1, end: 18 }]);
        setCustomStart('1'); setCustomEnd('18');
        setTeeTime('');
    };

    const togglePreset = (preset) => {
        setSelectedRanges(prev => {
            const exists = prev.find(r => r.start === preset.start && r.end === preset.end);
            if (exists) {
                // Remove it (but don't allow empty)
                const filtered = prev.filter(r => !(r.start === preset.start && r.end === preset.end));
                return filtered.length > 0 ? filtered : prev;
            }
            // If "Full 18" is being added, replace everything
            if (preset.start === 1 && preset.end === 18) {
                return [{ start: 1, end: 18 }];
            }
            // If adding a sub-range, remove "Full 18" if present
            const without18 = prev.filter(r => !(r.start === 1 && r.end === 18));
            return [...without18, { start: preset.start, end: preset.end }];
        });
    };

    const isPresetSelected = (preset) => {
        return selectedRanges.some(r => r.start === preset.start && r.end === preset.end);
    };

    const addCustomRange = () => {
        const s = parseInt(customStart);
        const e = parseInt(customEnd);
        if (s < 1 || e > 18 || s > e) return;
        if (selectedRanges.some(r => r.start === s && r.end === e)) return;
        const without18 = selectedRanges.filter(r => !(r.start === 1 && r.end === 18));
        setSelectedRanges([...without18, { start: s, end: e }]);
    };

    const removeRange = (idx) => {
        if (selectedRanges.length <= 1) return;
        setSelectedRanges(prev => prev.filter((_, i) => i !== idx));
    };

    const handleCreateMatchup = async (e) => {
        e.preventDefault();
        const teams = { A: [parseInt(teamA1)], B: [parseInt(teamB1)] };
        if (teamA2) teams.A.push(parseInt(teamA2));
        if (teamB2) teams.B.push(parseInt(teamB2));

        if (selectedRanges.length === 0) {
            setStatus('Select at least one hole range.');
            return;
        }

        try {
            const promises = selectedRanges.map(range =>
                backend.post('/matchups', {
                    format: mFormat,
                    use_handicaps: useHandicaps,
                    tee_id: parseInt(mTeeId),
                    teams,
                    points_for_win: parseFloat(pointsWin),
                    points_for_push: parseFloat(pointsPush),
                    hole_start: range.start,
                    hole_end: range.end,
                    tee_time: teeTime || undefined,
                })
            );
            await Promise.all(promises);
            const count = selectedRanges.length;
            setStatus(`Created ${count} matchup${count > 1 ? 's' : ''} successfully!`);
            resetForm();
            setShowCreate(false);
            fetchMatchups();
        } catch (e) {
            setStatus('Failed to create matchup.');
        }
    };

    const handleDeleteMatchup = async (id) => {
        if (!window.confirm('Delete this matchup? All associated scores will also be removed.')) return;
        try {
            await backend.delete(`/matchups/${id}`);
            setStatus('Matchup deleted.');
            fetchMatchups();
        } catch (e) {
            setStatus('Failed to delete matchup.');
        }
    };

    const FORMAT_BASES = {
        'match_play': 'Match Play',
        'stroke_play': 'Stroke Play',
        'scramble': 'Scramble'
    };

    // Compose a display label from backend data
    const getMatchupLabel = (m) => {
        const base = FORMAT_BASES[m.format] || m.format;
        const prefix = m.is_2v2 ? '2v2 ' : '';
        const hcap = m.use_handicaps ? ' · Net' : ' · Gross';
        return `${prefix}${base}${hcap}`;
    };

    const handleMatchupClick = (m) => {
        if (!m.first_player_id) {
            setStatus('Cannot edit: no players assigned to this matchup.');
            return;
        }
        // Impersonate player for play route
        localStorage.setItem('golf_player_id', String(m.first_player_id));
        localStorage.setItem('golf_player_name', m.first_player_name || 'Admin');
        
        const params = new URLSearchParams();
        if (m.tee_time) params.set('tee_time', m.tee_time);
        
        navigate(`/play/${m.tournament_id}/${m.tee_id}?${params.toString()}`);
    };

    // Hole range presets
    const HOLE_PRESETS = [
        { label: 'Full 18', start: 1, end: 18 },
        { label: 'Front 9', start: 1, end: 9 },
        { label: 'Back 9', start: 10, end: 18 },
        { label: 'Holes 1-6', start: 1, end: 6 },
        { label: 'Holes 7-12', start: 7, end: 12 },
        { label: 'Holes 13-18', start: 13, end: 18 },
    ];

    return (
        <div className="animate-slide-up">
            {/* Create Matchup Button */}
            {!showCreate && (
                <Card style={{ marginBottom: '1rem' }}>
                    <div className="matchups-top-bar">
                        <div>
                            <h3 style={{ margin: 0 }}>Matchups</h3>
                            <p className="matchups-subtitle">
                                {matchups.length} active matchup{matchups.length !== 1 ? 's' : ''}
                            </p>
                        </div>
                        <Button onClick={() => setShowCreate(true)}>+ New Matchup</Button>
                    </div>
                </Card>
            )}

            {/* Create Matchup Form */}
            {showCreate && (
                <Card style={{ marginBottom: '1rem' }} className="matchup-create-card">
                    <div className="matchup-create-header">
                        <h3 style={{ margin: 0 }}>Create Matchup</h3>
                        <button className="matchup-close-btn" onClick={() => { setShowCreate(false); resetForm(); }}>✕</button>
                    </div>

                    <form onSubmit={handleCreateMatchup} className="matchup-form">
                        {/* Tee Time */}
                        <div className="matchup-field">
                            <label>Tee Time</label>
                            <input
                                type="datetime-local"
                                value={teeTime}
                                onChange={e => setTeeTime(e.target.value)}
                                style={{ padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: '0.95rem', width: '100%' }}
                            />
                        </div>

                        {/* Format */}
                        <div className="matchup-field">
                            <label>Format</label>
                            <div className="format-toggle-row">
                                {Object.entries(FORMAT_BASES).map(([key, label]) => (
                                    <button
                                        key={key}
                                        type="button"
                                        className={`format-toggle-btn ${mFormat === key ? 'format-toggle-active' : ''}`}
                                        onClick={() => setMFormat(key)}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Handicap Toggle */}
                        <div className="matchup-field">
                            <label>Handicaps</label>
                            <div className="handicap-toggle">
                                <button
                                    type="button"
                                    className={`handicap-toggle-btn ${useHandicaps ? 'handicap-on' : ''}`}
                                    onClick={() => setUseHandicaps(true)}
                                >
                                    Net (With Handicaps)
                                </button>
                                <button
                                    type="button"
                                    className={`handicap-toggle-btn ${!useHandicaps ? 'handicap-off' : ''}`}
                                    onClick={() => setUseHandicaps(false)}
                                >
                                    Gross (No Handicaps)
                                </button>
                            </div>
                        </div>

                        {/* Course / Tee */}
                        <div className="matchup-field">
                            <label>Course & Tee</label>
                            <select value={mTeeId} onChange={e => setMTeeId(e.target.value)} required>
                                <option value="">Select a course and tee...</option>
                                {courses.flatMap(c => c.tees.map(t => (
                                    <option key={t.id} value={t.id}>{c.name} — {t.name}</option>
                                )))}
                            </select>
                        </div>

                        {/* Hole Ranges (Multi-Select) */}
                        <div className="matchup-field">
                            <label>Hole Ranges <span className="label-hint">Select one or more — each creates a matchup</span></label>
                            <div className="hole-presets">
                                {HOLE_PRESETS.map(p => (
                                    <button
                                        key={p.label}
                                        type="button"
                                        className={`hole-preset-btn ${isPresetSelected(p) ? 'hole-preset-active' : ''}`}
                                        onClick={() => togglePreset(p)}
                                    >
                                        {isPresetSelected(p) && <span className="preset-check">✓ </span>}
                                        {p.label}
                                    </button>
                                ))}
                            </div>

                            {/* Custom range adder */}
                            <div className="hole-range-custom">
                                <div className="hole-range-input-group">
                                    <span className="hole-range-label">From</span>
                                    <input
                                        type="number" min="1" max="18"
                                        value={customStart}
                                        onChange={e => setCustomStart(e.target.value)}
                                        className="hole-range-input"
                                    />
                                </div>
                                <span className="hole-range-dash">→</span>
                                <div className="hole-range-input-group">
                                    <span className="hole-range-label">To</span>
                                    <input
                                        type="number" min="1" max="18"
                                        value={customEnd}
                                        onChange={e => setCustomEnd(e.target.value)}
                                        className="hole-range-input"
                                    />
                                </div>
                                <button type="button" className="add-range-btn" onClick={addCustomRange}>+ Add</button>
                            </div>

                            {/* Selected ranges summary */}
                            {selectedRanges.length > 0 && (
                                <div className="selected-ranges">
                                    {selectedRanges.map((r, i) => (
                                        <span key={i} className="selected-range-chip">
                                            Holes {r.start}–{r.end}
                                            {selectedRanges.length > 1 && (
                                                <button type="button" className="range-chip-remove" onClick={() => removeRange(i)}>✕</button>
                                            )}
                                        </span>
                                    ))}
                                    <span className="range-summary">
                                        → {selectedRanges.length} matchup{selectedRanges.length > 1 ? 's' : ''} will be created
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Point Values */}
                        <div className="matchup-field">
                            <label>Point Values</label>
                            <div className="points-grid">
                                <div className="points-field">
                                    <span className="points-icon">🏆</span>
                                    <div>
                                        <span className="points-label">Win</span>
                                        <input
                                            type="number" step="0.5" min="0"
                                            value={pointsWin}
                                            onChange={e => setPointsWin(e.target.value)}
                                            className="points-input"
                                        />
                                    </div>
                                </div>
                                <div className="points-field">
                                    <span className="points-icon">🤝</span>
                                    <div>
                                        <span className="points-label">Push</span>
                                        <input
                                            type="number" step="0.5" min="0"
                                            value={pointsPush}
                                            onChange={e => setPointsPush(e.target.value)}
                                            className="points-input"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Players */}
                        <div className="matchup-field">
                            <label>Players</label>
                            <div className="players-draft-grid">
                                <div className="players-draft-team">
                                    <span className="draft-team-label">{teamAName}</span>
                                    <select value={teamA1} onChange={e => setTeamA1(e.target.value)} required className="draft-select">
                                        <option value="">Player 1...</option>
                                        {arrTeamA.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                        {arrUnassigned.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                    </select>
                                    <select value={teamA2} onChange={e => setTeamA2(e.target.value)} className="draft-select draft-select-optional">
                                        <option value="">Player 2 (opt)...</option>
                                        {arrTeamA.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                        {arrUnassigned.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                    </select>
                                </div>
                                <div className="players-draft-vs">VS</div>
                                <div className="players-draft-team">
                                    <span className="draft-team-label">{teamBName}</span>
                                    <select value={teamB1} onChange={e => setTeamB1(e.target.value)} required className="draft-select">
                                        <option value="">Player 1...</option>
                                        {arrTeamB.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                        {arrUnassigned.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                    </select>
                                    <select value={teamB2} onChange={e => setTeamB2(e.target.value)} className="draft-select draft-select-optional">
                                        <option value="">Player 2 (opt)...</option>
                                        {arrTeamB.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                        {arrUnassigned.map(p => <option key={p.id} value={p.id}>{p.name} ({p.handicap_index})</option>)}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <Button type="submit" style={{ width: '100%' }}>🚀 Launch Matchup</Button>
                    </form>
                </Card>
            )}

            {/* Matchup List */}
            <Card>
                {matchups.length === 0 && !showCreate && (
                    <div className="matchups-empty">
                        <div className="matchups-empty-icon">⚡</div>
                        <p>No matchups yet</p>
                        <span>Create your first matchup to get started!</span>
                    </div>
                )}

                <div className="matchup-list">
                    {matchups.map(m => (
                        <div 
                            key={m.id} 
                            className="matchup-card" 
                            style={{ cursor: 'pointer' }}
                            onClick={() => handleMatchupClick(m)}
                        >
                            <div className="matchup-card-header">
                                <div className="matchup-card-title-row">
                                    <span className="matchup-card-id">#{m.id}</span>
                                    <span className="matchup-format-badge">{getMatchupLabel(m)}</span>
                                    <span className="matchup-hole-badge">{m.hole_label}</span>
                                </div>
                                <button
                                    className="matchup-delete-btn"
                                    onClick={(e) => { e.stopPropagation(); handleDeleteMatchup(m.id); }}
                                    title="Delete matchup"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="matchup-card-course">
                                📍 {m.course} — {m.tee}
                                {m.tee_time && <span style={{ marginLeft: '0.5rem', opacity: 0.7 }}>🕐 {new Date(m.tee_time).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>}
                            </div>

                            <div className="matchup-card-teams">
                                <div className="matchup-team-col">
                                    <span className="matchup-team-name">{teamAName}</span>
                                    <span className="matchup-team-players">{m.teams['A']?.join(' & ') || '—'}</span>
                                </div>
                                <div className="matchup-vs-divider">
                                    <span>VS</span>
                                </div>
                                <div className="matchup-team-col matchup-team-col-right">
                                    <span className="matchup-team-name">{teamBName}</span>
                                    <span className="matchup-team-players">{m.teams['B']?.join(' & ') || '—'}</span>
                                </div>
                            </div>

                            {m.status === 'completed' && m.result && (
                                <div className={`matchup-result-banner ${m.result.winner === 'Push' ? 'result-push' : m.result.winner === 'A' ? 'result-team-a' : 'result-team-b'}`}>
                                    <div className="matchup-result-summary">
                                        <strong>{m.result.winner === 'Push' ? 'Match Halved' : `${m.result.winner === 'A' ? teamAName : teamBName} Wins`}</strong>
                                        <span> • {m.result.summary}</span>
                                    </div>
                                    <div className="matchup-result-points">
                                        Pts: {m.result.points_a} - {m.result.points_b}
                                    </div>
                                </div>
                            )}

                            <div className="matchup-card-footer">
                                <div className="matchup-points-display">
                                    <span className="matchup-point-chip matchup-point-win">
                                        🏆 {m.points_for_win} pt{m.points_for_win !== 1 ? 's' : ''}
                                    </span>
                                    <span className="matchup-point-chip matchup-point-push">
                                        🤝 {m.points_for_push} pt{m.points_for_push !== 1 ? 's' : ''}
                                    </span>
                                </div>
                                <span className={`matchup-status matchup-status-${m.status}`}>
                                    {m.status}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </Card>
        </div>
    );
}
