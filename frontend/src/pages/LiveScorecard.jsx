import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import backend from '../api/backend';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

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
        const fmt = format.charAt(0).toUpperCase() + format.slice(1);
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

            <header className="hole-header" style={{ marginBottom: 'var(--spacing-6)' }}>
                <h1 className="hole-number-label">{data.status_string}</h1>
                <p style={{ color: 'var(--color-text-light)', marginTop: 'var(--spacing-1)', fontWeight: 600 }}>
                    {data.display_thru}
                </p>
            </header>

            <Card className="animate-slide-up" style={{ padding: '0', overflow: 'hidden' }}>
                <table className="golf-scorecard-table" style={{ minWidth: '100%', margin: '0' }}>
                    <thead>
                        <tr style={{ background: 'rgba(0,0,0,0.02)' }}>
                            <th className="sc-label-cell">
                                <span className="sc-label-full">Hole</span>
                                <span className="sc-label-initials">H</span>
                            </th>
                            {data.scorecard.map(h => (
                                <th key={h.hole_number} className="sc-hole-header">{h.hole_number}</th>
                            ))}
                        </tr>
                        <tr>
                            <td className="sc-label-cell">
                                <span className="sc-label-full">Par</span>
                                <span className="sc-label-initials">P</span>
                            </td>
                            {data.scorecard.map(h => (
                                <td key={h.hole_number} style={{ fontSize: '0.7rem', color: 'var(--color-text-light)' }}>{h.par}</td>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="sc-match-row">
                            <td className="sc-label-cell">
                                <span className="sc-match-label-full">Match</span>
                            </td>
                            {(() => {
                                let running = 0;
                                return data.scorecard.map(h => {
                                    if (h.winner === 'A') running++;
                                    else if (h.winner === 'B') running--;
                                    
                                    let display = '–';
                                    let className = '';
                                    if (h.winner) {
                                        display = running === 0 ? 'AS' : (running > 0 ? `+${running}` : running);
                                        if (h.winner === 'A') className = 'sc-match-won';
                                        else if (h.winner === 'B') className = 'sc-match-lost';
                                    }
                                    return <td key={h.hole_number} className={`sc-match-cell ${className}`} style={{ fontWeight: 700 }}>{display}</td>
                                });
                            })()}
                        </tr>
                    </tbody>
                </table>
            </Card>

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
