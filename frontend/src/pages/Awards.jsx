import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
    Award, 
    Crown, 
    Target, 
    Ghost, 
    Skull, 
    Trophy, 
    Bomb,
    TrendingUp,
    Medal,
    Flame,
    Bird,
    Sparkles,
    ChevronRight,
    Backpack
} from 'lucide-react';

const EagleIcon = () => (
    <svg 
        viewBox="0 0 24 24" 
        width="28" 
        height="28" 
        fill="none" 
        stroke="currentColor" 
        strokeWidth="2.2" 
        strokeLinecap="round" 
        strokeLinejoin="round"
        className="lucide lucide-eagle"
    >
        <path d="M11 6c.5-.7 1.5-.7 2 0l1 1.5M10 9h4" />
        <path d="M12 8C7 5 3 6.5 1 8.5c4.5 3.5 8.5 3 11 .5" />
        <path d="M12 8c5-3 9-1.5 11 .5-4.5 3.5-8.5 3-11 .5" />
        <path d="M9 16c1.5 2 4.5 2 6 0l-3 4-3-4z" />
    </svg>
);
import backend from '../api/backend';
import PlayerAvatar from '../components/ui/PlayerAvatar';
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

    // 1. Determine overall winning team ('A' or 'B', or null if tied)
    const winningTeam = competition.team_a_points > competition.team_b_points 
        ? 'A' 
        : (competition.team_b_points > competition.team_a_points ? 'B' : null);

    // 2. Find the top-ranked player on the winning team,
    // or if teams are tied, simply the top-ranked player overall.
    // player_stats is already sorted in descending performance order by the backend.
    const mvpPlayer = winningTeam 
        ? player_stats.find(s => s.team === winningTeam) 
        : player_stats[0];
    
    const mvpPlayerId = mvpPlayer ? mvpPlayer.player_id : null;

    const getRankBadge = (rank) => {
        let highlightClass = '';
        if (rank === 1) highlightClass = 'rank-gold';
        else if (rank === 2) highlightClass = 'rank-silver';
        else if (rank === 3) highlightClass = 'rank-bronze';
        
        return (
            <span className={`stat-rank ${highlightClass}`}>
                #{rank}
            </span>
        );
    };

    return (
        <div className="awards-container animate-slide-up">
            <header className="awards-header">
                <div className="header-glow"></div>
                <span className="awards-subtitle">{competition.name}</span>
                <h1>Leaderboard & Accolades</h1>
            </header>

            {/* Full Leaderboard / Standings Section - NOW AT THE TOP! */}
            <section className="stats-section">
                <h2 className="section-title">
                    <Medal size={20} className="section-title-icon" />
                    <span>Full Standings</span>
                </h2>
                <div className="stats-grid">
                    {player_stats.length === 0 ? (
                        <div className="list-empty">No standings recorded yet.</div>
                    ) : (
                        player_stats.map((s, i) => {
                            const isMVP = s.player_id === mvpPlayerId;
                            const isTopThree = i < 3;
                            return (
                                <div
                                    key={s.player_id}
                                    className={`stat-row animate-slide-up team-${s.team.toLowerCase()} ${isMVP ? 'mvp-row' : ''} ${isTopThree ? `top-three-row rank-${i+1}` : ''}`}
                                    style={{ animationDelay: `${0.05 + (i * 0.04)}s`, cursor: 'pointer' }}
                                    onClick={() => navigate(`/player-stats/${s.player_id}`)}
                                >
                                    <div className="stat-player-info">
                                        {getRankBadge(i + 1)}
                                        <div className="avatar-wrapper">
                                            <PlayerAvatar name={s.name} image={s.profile_picture} size="sm" />
                                            {isMVP && <div className="avatar-mvp-crown"><Crown size={12} fill="currentColor" /></div>}
                                        </div>
                                        <div className="stat-name-group">
                                            <div className="stat-name-wrapper">
                                                <span className="stat-name">{s.name}</span>
                                                {isMVP && (
                                                    <span className="mvp-tag">
                                                        <Crown size={10} fill="currentColor" />
                                                        <span>MVP</span>
                                                    </span>
                                                )}
                                            </div>
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
                                    
                                    <div className="row-chevron">
                                        <ChevronRight size={14} />
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </section>

            {/* Accolades Section - NOW BELOW THE STANDINGS! */}
            <section className="accolades-section">
                <h2 className="section-title">
                    <Sparkles size={20} className="section-title-icon" />
                    <span>Tournament Accolades</span>
                </h2>
                <div className="accolades-grid">
                    {/* Note: Tournament MVP card has been removed as requested. MVP tag is now on the standings list. */}
                    
                    {awards.eagle_king && !awards.eagle_king.hidden && (
                        <AwardCard 
                            title="Eagle King" 
                            award={awards.eagle_king} 
                            icon={<EagleIcon />} 
                            className="eagle-award"
                        />
                    )}
                    <AwardCard 
                        title="Birdie King" 
                        award={awards.birdie_king} 
                        icon={<Bird size={24} />} 
                        className="birdie-award"
                    />
                    <AwardCard 
                        title="Net Birdie King" 
                        award={awards.net_birdie_king} 
                        icon={<Target size={24} />} 
                        className="net-birdie-award"
                    />
                    <AwardCard 
                        title="Best Golfer" 
                        award={awards.best_golfer} 
                        icon={<Award size={24} />} 
                        className="best-golfer-award"
                    />
                    {awards.matchplay_blowout && !awards.matchplay_blowout.hidden && (
                        <AwardCard 
                            title="Matchplay Blowout" 
                            award={awards.matchplay_blowout} 
                            icon={<Flame size={24} />} 
                            className="blowout-award"
                        />
                    )}
                    {awards.freeloader && !awards.freeloader.hidden && (
                        <AwardCard 
                            title="Freeloader" 
                            award={awards.freeloader} 
                            icon={<Backpack size={24} />} 
                            className="freeloader-award"
                        />
                    )}

                    {!awards.worst_hole.hidden && (
                        <AwardCard 
                            title="Worst Hole" 
                            award={awards.worst_hole} 
                            icon={<Skull size={24} />} 
                            className="worst-hole-award"
                        />
                    )}
                    <AwardCard 
                        title="Best Round (Net)" 
                        award={awards.best_round} 
                        icon={<Trophy size={24} />} 
                        className="best-round-award"
                    />
                    <AwardCard 
                        title="Best Round (Gross)" 
                        award={awards.best_round_gross} 
                        icon={<Trophy size={24} />} 
                        className="best-round-gross-award"
                    />
                    <AwardCard 
                        title="Worst Round (Net)" 
                        award={awards.worst_round} 
                        icon={<Bomb size={24} />} 
                        className="worst-round-award"
                    />
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
            const params = new URLSearchParams();
            if (award.player_id) params.set('player_id', award.player_id);
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
            <div className="award-glow"></div>
            <div className="award-icon-container">
                {icon}
            </div>
            <div className="award-content">
                <h3 className="award-title">{title}</h3>
                <div className="award-winner-group">
                    <PlayerAvatar name={award.name} image={award.profile_picture} size="sm" />
                    <div className="award-winner">
                        <span className="winner-name-text">{award.name}</span>
                        {award.is_tie && <span className="award-tie-badge">Tie</span>}
                    </div>
                </div>
                <div className="award-values">
                    <span className="award-main-value">{award.value}</span>
                    {award.subtext && <span className="award-subtext">{award.subtext}</span>}
                </div>
            </div>
            {isClickable && (
                <div className="award-card-action">
                    <ChevronRight size={14} />
                </div>
            )}
        </div>
    );
}
