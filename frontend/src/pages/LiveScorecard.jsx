import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import backend from '../api/backend';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import './ViewScorecard.css';


export default function LiveScorecard() {
    const { matchupId } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchMatchup();
        const interval = setInterval(fetchMatchup, 30000);
        return () => clearInterval(interval);
    }, [matchupId]);

    const fetchMatchup = async () => {
        try {
            const res = await backend.get(`/matchups/${matchupId}`);
            setData(res.data);
        } catch (e) {
            console.error('Failed to fetch matchup', e);
        } finally {
            setLoading(false);
        }
    };

    const formatMatchName = (format, scoring) => {
        if (!format || !scoring) return '';
        const fmt = format.replace(/_/g, ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.substring(1)).join(' ');
        const scr = scoring === 'match_play' ? 'Match Play' : 'Stroke Play';
        return `${fmt} ${scr} Net`;
    };

    const getInitials = (name) => {
        if (!name) return '';
        return name.split(' ').map(part => part[0]).join('').toUpperCase();
    };

    if (loading && !data) {
        return (
            <div className="play-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading live match...</span>
                </div>
            </div>
        );
    }

    if (!data || data.error) {
        return (
            <div className="play-container">
                <div style={{ textAlign: 'center', padding: 'var(--spacing-10)' }}>
                    <h2>Match not found</h2>
                    <Button onClick={() => navigate('/leaderboard')}>Back to Leaderboard</Button>
                </div>
            </div>
        );
    }

    return (
        <div className="play-container animate-slide-up">
            <div className="play-top-bar">
                <button className="play-back-btn" onClick={() => navigate(-1)}>
                    ← Back
                </button>
                {data.format && (
                    <span className="match-format-badge">
                        {formatMatchName(data.format, data.scoring_type)}
                    </span>
                )}
            </div>

            <header className="hole-header" style={{ marginBottom: 'var(--spacing-6)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {data.course_logo ? (
                    <img src={data.course_logo} alt="course logo" style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '50%', marginBottom: '0.5rem', border: '2px solid var(--color-border)' }} />
                ) : (
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>⛳️</div>
                )}
                <h1 className="hole-number-label" style={{ margin: 0 }}>{data.status_string}</h1>
                <p style={{ color: 'var(--color-text-light)', marginTop: 'var(--spacing-1)', fontWeight: 600, margin: 0 }}>
                    {data.display_thru}
                </p>
            </header>

            {(() => {
                const totalHoles = data.scorecard.length;
                const splitPoint = totalHoles <= 9 ? totalHoles : Math.ceil(totalHoles / 2);
                const front9 = data.scorecard.filter(h => h.hole_number <= splitPoint);
                const back9 = data.scorecard.filter(h => h.hole_number > splitPoint);

                // Precompute running totals so they carry over
                const runningScores = {};
                let currentRunning = 0;
                data.scorecard.forEach(h => {
                    if (h.winner === 'A') currentRunning++;
                    else if (h.winner === 'B') currentRunning--;
                    runningScores[h.hole_number] = currentRunning;
                });

                const renderTable = (holes, label) => {
                    if (holes.length === 0) return null;
                    return (
                        <Card className="animate-slide-up" style={{ padding: '0', overflow: 'hidden', marginBottom: 'var(--spacing-4)' }}>
                            <table className="sc-table" style={{ minWidth: '100%', margin: '0' }}>
                                <thead>
                                    <tr className="sc-header-row">
                                        <th className="sc-label">
                                            <span className="sc-label-full">{label}</span>
                                            <span className="sc-label-initials">{label === 'OUT' ? 'O' : 'I'}</span>
                                        </th>
                                        {holes.map(h => (
                                            <th key={h.hole_number} className="sc-hole-header">{h.hole_number}</th>
                                        ))}
                                    </tr>
                                    <tr className="sc-par-row">
                                        <td className="sc-label">
                                            <span className="sc-label-full">Par</span>
                                            <span className="sc-label-initials">P</span>
                                        </td>
                                        {holes.map(h => (
                                            <td key={h.hole_number} style={{ fontSize: '0.7rem', color: 'var(--color-text-light)' }}>{h.par}</td>
                                        ))}
                                    </tr>
                                    <tr className="sc-yard-row">
                                        <td className="sc-label">
                                            <span className="sc-label-full">Yard</span>
                                            <span className="sc-label-initials">Y</span>
                                        </td>
                                        {holes.map(h => (
                                            <td key={h.hole_number} style={{ fontSize: '0.7rem', color: 'var(--color-text-light)' }}>{h.yardage || '–'}</td>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="sc-match-row">
                                        <td className="sc-label">
                                            <span className="sc-match-label-full">Match</span>
                                            <span className="sc-label-initials">M</span>
                                        </td>
                                        {holes.map(h => {
                                            const running = runningScores[h.hole_number];
                                            let display = '–';
                                            let className = '';
                                            if (h.winner) {
                                                display = running === 0 ? 'AS' : (running > 0 ? `+${running}` : running);
                                                if (h.winner === 'A') className = 'sc-match-won';
                                                else if (h.winner === 'B') className = 'sc-match-lost';
                                            } else if (h.decided_status) {
                                                display = h.decided_status;
                                            }
                                            return <td key={h.hole_number} className={`sc-match-cell ${className}`} style={{ fontWeight: 700 }}>{display}</td>
                                        })}
                                    </tr>
                                </tbody>
                            </table>
                        </Card>
                    );
                };

                return (
                    <>
                        {renderTable(front9, 'OUT')}
                        {renderTable(back9, 'IN')}
                    </>
                );
            })()}

            <div style={{ marginTop: 'var(--spacing-8)', textAlign: 'center' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: 'var(--spacing-4)' }}>
                    Detailed handicaps and scores are available on the full scorecard.
                </p>
                <Button 
                    variant="outline" 
                    style={{ width: '100%' }}
                    onClick={() => navigate('/leaderboard')}
                >
                    View Overall Leaderboard
                </Button>
            </div>
        </div>
    );
}
