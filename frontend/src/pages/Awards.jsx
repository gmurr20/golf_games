import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
    Award, 
    Crown, 
    Zap, 
    Target, 
    Ghost, 
    UserCheck, 
    Skull, 
    Trophy, 
    Bomb,
    TrendingUp,
    Medal
} from 'lucide-react';
import backend from '../api/backend';
import './Awards.css';

export default function Awards() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        fetchAwards();
        const interval = setInterval(fetchAwards, 60000);
        return () => clearInterval(interval);
    }, []);

    const fetchAwards = async () => {
        try {
            const res = await backend.get('/leaderboard');
            setData(res.data);
        } catch (e) {
            console.error('Failed to fetch awards', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <div className="awards-container">
                <div className="home-loading">
                    <div className="spinner"></div>
                    <span>Loading accolades...</span>
                </div>
            </div>
        );
    }

    if (!data) return null;

    const { competition, player_stats, awards } = data;

    return (
        <div className="awards-container animate-slide-up">
            <header className="awards-header">
                <h1>The Hall of Fame</h1>
                <p>{competition.name} Awards & Accolades</p>
            </header>

            {/* Accolades Section */}
            <section className="accolades-section">
                <div className="accolades-grid">
                    <AwardCard 
                        title="Tournament MVP" 
                        award={awards.mvp} 
                        icon={<Crown size={32} />} 
                        className="mvp-award"
                    />
                    <AwardCard 
                        title="Birdie King" 
                        award={awards.birdie_king} 
                        icon={<Zap size={32} />} 
                        className="birdie-award"
                    />
                    <AwardCard 
                        title="Net Birdie King" 
                        award={awards.net_birdie_king} 
                        icon={<Target size={32} />} 
                        className="net-birdie-award"
                    />
                    <AwardCard 
                        title="Biggest Sandbagger" 
                        award={awards.sandbagger} 
                        icon={<Ghost size={32} />} 
                        className="sandbagger-award"
                    />
                    <AwardCard 
                        title="Most Honest" 
                        award={awards.most_honest} 
                        icon={<UserCheck size={32} />} 
                        className="honest-award"
                    />
                    {!awards.worst_hole.hidden && (
                        <AwardCard 
                            title="Worst Hole" 
                            award={awards.worst_hole} 
                            icon={<Skull size={32} />} 
                            className="worst-hole-award"
                        />
                    )}
                    <AwardCard 
                        title="Best Round (Net)" 
                        award={awards.best_round} 
                        icon={<Trophy size={32} />} 
                        className="best-round-award"
                    />
                    <AwardCard 
                        title="Worst Round (Net)" 
                        award={awards.worst_round} 
                        icon={<Bomb size={32} />} 
                        className="worst-round-award"
                    />
                </div>
            </section>

            {/* Full Leaderboard Section */}
            <section className="stats-section">
                <h2 className="section-title"><Medal size={20} /> Full Standings</h2>
                <div className="stats-grid">
                    {player_stats.length === 0 ? (
                        <div className="list-empty">No stats recorded yet.</div>
                    ) : (
                        player_stats.map((s, i) => (
                            <div
                                key={s.player_id}
                                className={`stat-row animate-slide-up team-${s.team.toLowerCase()}`}
                                style={{ animationDelay: `${0.1 + (i * 0.05)}s`, cursor: 'pointer' }}
                                onClick={() => navigate(`/player-stats/${s.player_id}`)}
                            >
                                <div className="stat-player-info">
                                    <span className="stat-rank">#{i + 1}</span>
                                    <div className="stat-name-group">
                                        <span className="stat-name">{s.name}</span>
                                        <span className={`stat-team-badge team-${s.team.toLowerCase()}`}>
                                            {s.team_display_name}
                                        </span>
                                    </div>
                                </div>

                                <div className="stat-metrics">
                                    <div className="stat-metric-block">
                                        <span className="metric-label">GROSS</span>
                                        <span className={`metric-value ${s.gross_to_par === 'E' ? 'even' : s.gross_to_par.startsWith('-') ? 'under' : 'over'}`}>
                                            {s.gross_to_par}
                                        </span>
                                    </div>
                                    <div className="stat-metric-block">
                                        <span className="metric-label">NET</span>
                                        <span className={`metric-value ${s.net_to_par === 'E' ? 'even' : s.net_to_par.startsWith('-') ? 'under' : 'over'}`}>
                                            {s.net_to_par}
                                        </span>
                                    </div>
                                </div>

                                <div className="stat-value-container">
                                    <div className="stat-value">{s.wins}-{s.losses}-{s.ties}</div>
                                    <div className="stat-label">{s.points_earned} PTS</div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}

function AwardCard({ title, award, icon, className }) {
    const navigate = useNavigate();
    if (!award) return null;

    const handleClick = () => {
        if (award.tournament_id && award.tee_id) {
            // Round awards link to scorecard with tee_time filter
            const params = new URLSearchParams();
            if (award.tee_time) params.set('tee_time', award.tee_time);
            navigate(`/view-scorecard/${award.tournament_id}/${award.tee_id}?${params.toString()}`);
        } else if (award.player_id) {
            // Player awards link to player stats
            navigate(`/player-stats/${award.player_id}`);
        }
    };

    const isClickable = award.player_id || (award.tournament_id && award.tee_id);

    return (
        <div 
            className={`award-card animate-slide-up ${className} ${isClickable ? 'clickable' : ''}`}
            onClick={isClickable ? handleClick : undefined}
        >
            <div className="award-icon-container">
                {icon}
            </div>
            <div className="award-content">
                <h3 className="award-title">{title}</h3>
                <div className="award-winner">
                    {award.name}
                    {award.is_tie && <span className="award-tie-badge">Tie</span>}
                </div>
                <div className="award-values">
                    <span className="award-main-value">{award.value}</span>
                    {award.subtext && <span className="award-subtext">{award.subtext}</span>}
                </div>
            </div>
        </div>
    );
}
