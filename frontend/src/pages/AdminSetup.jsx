import React, { useState, useEffect, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import CoursesTab from '../components/CoursesTab';
import MatchupsTab from '../components/MatchupsTab';
import PlayerAvatar from '../components/ui/PlayerAvatar';
import backend, { setAdminKey } from '../api/backend';
import './AdminSetup.css';

export default function AdminSetup() {
    const [dashboardMode, setDashboardMode] = useState(false);
    const [password, setPassword] = useState('');
    const [status, setStatus] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const stored = localStorage.getItem('golf_admin_key');
        if (stored) {
            setAdminKey(stored);
            // Validate stored key is still valid
            backend.get('/competitions/settings').then(() => {
                setDashboardMode(true);
            }).catch(() => {
                localStorage.removeItem('golf_admin_key');
                setAdminKey(null);
            });
        }
    }, []);

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setStatus('');
        try {
            const res = await backend.post('/auth', { password });
            setAdminKey(res.data.admin_key);
            localStorage.setItem('golf_admin_key', res.data.admin_key);
            setDashboardMode(true);
        } catch (error) {
            setStatus('Wrong password.');
        } finally {
            setLoading(false);
        }
    };

    if (!dashboardMode) {
        return (
            <div className="admin-login-container">
                <Card className="login-card animate-slide-up">
                    <div className="login-icon">🔒</div>
                    <h2 style={{ margin: '0 0 0.25rem 0', color: 'var(--color-text)' }}>Admin</h2>
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: '1.5rem' }}>Enter the password to continue</p>
                    <form onSubmit={handleLogin} className="login-form">
                        <input
                            type="password"
                            required
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Password"
                            autoFocus
                            className="login-input"
                        />
                        <Button type="submit" disabled={loading}>
                            {loading ? 'Unlocking...' : 'Unlock'}
                        </Button>
                    </form>
                    {status && <div style={{ marginTop: '1rem', color: 'var(--color-accent-lose)', fontSize: '0.85rem' }}>{status}</div>}
                </Card>
            </div>
        );
    }

    return <Dashboard />;
}

function Dashboard() {
    const [tab, setTab] = useState('matchups');
    const [status, setStatus] = useState('');
    const fileRef = useRef(null);
    const photoRef = useRef(null);
    const [uploadingPlayerId, setUploadingPlayerId] = useState(null);

    // Core Data
    const [players, setPlayers] = useState([]);
    const [courses, setCourses] = useState([]);
    const [matchups, setMatchups] = useState([]);

    // Global Team Settings
    const [teamAName, setTeamAName] = useState('Team A');
    const [teamBName, setTeamBName] = useState('Team B');
    const [isEditingTeams, setIsEditingTeams] = useState(false);

    // Player Form State
    const [editPlayerId, setEditPlayerId] = useState(null);
    const [pName, setPName] = useState('');
    const [pIndex, setPIndex] = useState('');
    const [pTeam, setPTeam] = useState('');
    const [pGender, setPGender] = useState('male');
    const [pPhoto, setPPhoto] = useState(null);

    const fetchConfig = async () => {
        try {
            const res = await backend.get('/competitions/settings');
            setTeamAName(res.data.team_a_name);
            setTeamBName(res.data.team_b_name);
        } catch (e) { }
    };

    const fetchPlayers = async () => {
        try {
            const res = await backend.get('/players');
            setPlayers(res.data);
        } catch (e) {
            console.error("No active players yet.");
        }
    };

    const fetchCourses = async () => {
        try {
            const res = await backend.get('/courses');
            setCourses(res.data);
        } catch (e) {
            console.error("No active courses yet.");
        }
    };

    const fetchMatchups = async () => {
        try {
            const res = await backend.get('/matchups');
            setMatchups(res.data);
        } catch (e) { }
    };

    useEffect(() => {
        fetchConfig();
        fetchPlayers();
        fetchCourses();
        fetchMatchups();
    }, []);

    // Clear status when switching tabs
    useEffect(() => {
        setStatus('');
    }, [tab]);

    // CONFIG EDITING
    const saveTeamConfig = async () => {
        await backend.put('/competitions/settings', { team_a_name: teamAName, team_b_name: teamBName });
        setIsEditingTeams(false);
        setStatus("Team Names globally updated!");
    };

    // DRAG AND DROP HANDLERS
    const handleDragStart = (e, p) => {
        e.dataTransfer.setData('playerId', p.id.toString());
        // Custom styling for the dragged element could be added here
        e.target.style.opacity = '0.5';
    };

    const handleDragEnd = (e) => {
        e.target.style.opacity = '1';
    };

    const handleDragOver = (e) => {
        e.preventDefault(); // Necessary to allow dropping
    };

    const handleDrop = async (e, targetTeam) => {
        e.preventDefault();
        const playerIdStr = e.dataTransfer.getData('playerId');
        if (!playerIdStr) return;
        const playerId = parseInt(playerIdStr);

        // Optimistic UI Update so it snaps instantly
        setPlayers(prev => prev.map(p => p.id === playerId ? { ...p, team: targetTeam } : p));

        // Async Backend Call
        try {
            await backend.put(`/players/${playerId}`, { team: targetTeam });
        } catch (error) {
            setStatus("Failed to move player. Try again.");
            fetchPlayers(); // Revert on failure
        }
    };

    // CRUD PLAYER OPERATIONS
    const handleAddOrEditPlayer = async (e) => {
        e.preventDefault();
        try {
            if (editPlayerId) {
                await backend.put(`/players/${editPlayerId}`, {
                    name: pName,
                    handicap_index: parseFloat(pIndex),
                    team: pTeam,
                    gender: pGender,
                    profile_picture: pPhoto
                });
                setStatus(`Updated Player: ${pName}`);
            } else {
                await backend.post('/players', {
                    name: pName,
                    handicap_index: parseFloat(pIndex),
                    team: pTeam,
                    gender: pGender,
                    profile_picture: pPhoto
                });
                setStatus(`Added Player: ${pName}`);
            }
            setEditPlayerId(null);
            setPName(''); setPIndex(''); setPTeam(''); setPPhoto(null);
            fetchPlayers();
        } catch (e) {
            setStatus('Error saving player.');
        }
    };

    const handleEditClick = (p) => {
        setEditPlayerId(p.id);
        setPName(p.name);
        setPIndex(p.handicap_index);
        setPTeam(p.team || '');
        setPGender(p.gender || 'male');
        setPPhoto(p.profile_picture || null);
    };

    const handleDeleteClick = async (id) => {
        if (!window.confirm("Are you sure you want to delete this player? This will also remove any matchups they are part of.")) return;
        await backend.delete(`/players/${id}`);
        setStatus('Player deleted.');
        fetchPlayers();
    };

    const handlePhotoChange = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setStatus('Processing photo...');
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const size = 400;
                canvas.width = size;
                canvas.height = size;
                const ctx = canvas.getContext('2d');

                let srcX = 0, srcY = 0, srcW = img.width, srcH = img.height;
                if (srcW > srcH) {
                    srcX = (srcW - srcH) / 2;
                    srcW = srcH;
                } else {
                    srcY = (srcH - srcW) / 2;
                    srcH = srcW;
                }

                ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, size, size);
                const base64 = canvas.toDataURL('image/jpeg', 0.85);
                setPPhoto(base64);
                setStatus('Photo ready to save.');
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    };

    const handlePhotoClick = (playerId) => {
        setUploadingPlayerId(playerId);
        photoRef.current.click();
    };

    // (Removed old standalone photo handling logic from here, now in handlePhotoChange)

    // AI PROCESSOR
    const handleUploadScorecard = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setStatus('Processing via AI... this can take up to a minute.');
        const formData = new FormData();
        formData.append('image', file);

        try {
            const res = await backend.post('/courses/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const parsed = res.data;
            setStatus(`AI Parsed: ${parsed.course_name}. Saving directly to PostgreSQL...`);

            await backend.post('/courses', {
                name: parsed.course_name,
                tees: parsed.tees.map(tee => ({
                    name: tee.tee_name,
                    rating: tee.rating,
                    slope: tee.slope,
                    rating_female: tee.rating_female,
                    slope_female: tee.slope_female,
                    par: tee.holes.reduce((a, b) => a + Number(b.par), 0),
                    holes: tee.holes
                }))
            });

            if (parsed.warnings && parsed.warnings.length > 0) {
                const warnMsg = `Success, but with warnings:\n\n${parsed.warnings.join('\n')}\n\nPlease verify these ratings manually in the Courses tab.`;
                window.alert(warnMsg);
                setStatus(warnMsg);
            } else {
                setStatus(`Success! AI Documented ${parsed.course_name} with ${parsed.tees.length} tees.`);
            }
            fetchCourses();
        } catch (error) {
            console.error(error);
            setStatus('Failed to parse image. Is Gemini API configured properly?');
        }
    };




    const handleLogout = () => {
        localStorage.removeItem('golf_admin_key');
        setAdminKey(null);
        window.location.reload();
    };

    // Derived Team Arrays
    const arrTeamA = players.filter(p => p.team === teamAName);
    const arrTeamB = players.filter(p => p.team === teamBName);
    const arrUnassigned = players.filter(p => p.team !== teamAName && p.team !== teamBName);

    const PlayerList = ({ title, list, dropTarget }) => (
        <div
            style={{
                marginBottom: '1.5rem',
                minHeight: '100px',
                padding: '0.75rem',
                backgroundColor: 'rgba(0,0,0,0.02)',
                border: '2px dashed transparent',
                borderRadius: '12px'
            }}
            onDrop={(e) => { e.currentTarget.style.borderColor = 'transparent'; handleDrop(e, dropTarget); }}
            onDragOver={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-light)'; handleDragOver(e); }}
            onDragLeave={(e) => { e.currentTarget.style.borderColor = 'transparent'; }}
        >
            <h4 style={{ marginBottom: '0.75rem', color: 'var(--color-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.35rem' }}>
                {title} ({list.length})
            </h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {list.map(p => (
                    <li
                        key={p.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, p)}
                        onDragEnd={handleDragEnd}
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: 'var(--color-surface)',
                            borderRadius: '8px',
                            marginBottom: '0.5rem',
                            cursor: 'grab',
                            boxShadow: 'var(--shadow-sm)',
                            border: '1px solid var(--color-border)',
                            transition: 'box-shadow 0.2s ease, transform 0.15s ease'
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.boxShadow = 'var(--shadow-md)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                            <div style={{
                                minWidth: '52px',
                                height: '36px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                borderRadius: 'var(--radius-pill)',
                                background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-light))',
                                color: '#fff',
                                fontSize: '0.85rem',
                                fontWeight: 700,
                                letterSpacing: '-0.3px',
                                boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                                flexShrink: 0,
                                padding: '0 10px'
                            }}>
                                {p.handicap_index}
                            </div>
                            <PlayerAvatar name={p.name} image={p.profile_picture} size="sm" />
                            <strong style={{ fontSize: '0.95rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--color-text)' }}>{p.name}</strong>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                            <Button variant="outline" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => handleEditClick(p)}>✏️</Button>
                            <Button variant="outline" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', borderColor: 'var(--color-accent-lose)', color: 'var(--color-accent-lose)' }} onClick={() => handleDeleteClick(p.id)}>X</Button>
                        </div>
                    </li>
                ))}
                {list.length === 0 && <p style={{ fontSize: '0.8rem', color: 'var(--color-text-light)', fontStyle: 'italic', textAlign: 'center', padding: '1rem 0' }}>Drag players here...</p>}
            </ul>
        </div>
    );

    return (
        <div className="admin-dashboard-container">
            <header className="admin-header">
                <div className="admin-header-title-group">
                    <span className="admin-subtitle">Control Center</span>
                    <h1>Contest Creator</h1>
                </div>
                <Button variant="outline" onClick={handleLogout} style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}>Log Out</Button>
            </header>

            <div className="admin-tabs-wrapper">
                <div className="admin-tabs">
                    <button 
                        className={`tab-btn ${tab === 'players' ? 'active' : ''}`}
                        onClick={() => setTab('players')}
                    >
                        Players
                    </button>
                    <button 
                        className={`tab-btn ${tab === 'courses' ? 'active' : ''}`}
                        onClick={() => setTab('courses')}
                    >
                        Courses
                    </button>
                    <button 
                        className={`tab-btn ${tab === 'matchups' ? 'active' : ''}`}
                        onClick={() => setTab('matchups')}
                    >
                        Matchups
                    </button>
                </div>
            </div>

            {status && <div className="status-banner"><span>✨</span> {status}</div>}

            {tab === 'players' && (
                <Card className="animate-slide-up">
                    <h3 style={{ color: editPlayerId ? 'var(--color-accent-win)' : 'var(--color-text)', marginBottom: 'var(--spacing-4)' }}>
                        {editPlayerId ? '✏️ Editing Player' : '➕ Add Player'}
                    </h3>
                    <form onSubmit={handleAddOrEditPlayer} className="player-form">
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                            <div style={{ position: 'relative', cursor: 'pointer' }} onClick={() => photoRef.current.click()}>
                                <PlayerAvatar name={pName || '?'} image={pPhoto} size="lg" />
                                <div style={{
                                    position: 'absolute',
                                    bottom: 0,
                                    right: 0,
                                    background: 'var(--color-primary)',
                                    color: 'white',
                                    borderRadius: '50%',
                                    width: '24px',
                                    height: '24px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    fontSize: '0.7rem',
                                    border: '2px solid white'
                                }}>
                                    📷
                                </div>
                            </div>
                            <div style={{ flex: 1 }}>
                                <input type="text" placeholder="Name" value={pName} onChange={e => setPName(e.target.value)} className="form-input" style={{ marginBottom: '0.5rem' }} required />
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <Button type="button" variant="outline" style={{ fontSize: '0.7rem', padding: '4px 8px' }} onClick={() => photoRef.current.click()}>
                                        {pPhoto ? 'Change Photo' : 'Add Photo'}
                                    </Button>
                                    {pPhoto && (
                                        <Button type="button" variant="outline" style={{ fontSize: '0.7rem', padding: '4px 8px', borderColor: 'var(--color-accent-lose)', color: 'var(--color-accent-lose)' }} onClick={() => setPPhoto(null)}>
                                            Remove
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                        <div className="form-row">
                            <input type="number" step="0.1" placeholder="Handicap Index" value={pIndex} onChange={e => setPIndex(e.target.value)} className="form-input" required />
                            <select value={pTeam} onChange={e => setPTeam(e.target.value)} className="form-select">
                                <option value="">No Team</option>
                                <option value={teamAName}>{teamAName}</option>
                                <option value={teamBName}>{teamBName}</option>
                            </select>
                        </div>
                        <div className="form-row">
                            <div className="gender-toggle">
                                <button
                                    type="button"
                                    onClick={() => setPGender('male')}
                                    className={`gender-btn ${pGender === 'male' ? 'active' : ''}`}
                                >
                                    ♂ Male
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setPGender('female')}
                                    className={`gender-btn ${pGender === 'female' ? 'active' : ''}`}
                                >
                                    ♀ Female
                                </button>
                            </div>
                            <div style={{ flex: 1 }}></div>
                        </div>

                        <div className="form-row">
                            <Button type="submit" style={{ flex: 1 }}>{editPlayerId ? 'Save Changes' : 'Create Player'}</Button>
                            {editPlayerId && <Button variant="outline" onClick={() => { setEditPlayerId(null); setPName(''); setPIndex(''); setPTeam(''); setPPhoto(null); }}>Cancel</Button>}
                        </div>
                    </form>

                    <div className="roster-header">
                        <h3>Roster Builder</h3>
                        <Button variant="outline" style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }} onClick={() => setIsEditingTeams(!isEditingTeams)}>
                            {isEditingTeams ? 'Cancel Config' : '⚙️ Rename Teams'}
                        </Button>
                    </div>

                    {isEditingTeams && (
                        <div className="team-config-box">
                            <input type="text" value={teamAName} onChange={e => setTeamAName(e.target.value)} className="form-input" placeholder="Team 1 Name" />
                            <input type="text" value={teamBName} onChange={e => setTeamBName(e.target.value)} className="form-input" placeholder="Team 2 Name" />
                            <Button onClick={saveTeamConfig}>Save</Button>
                        </div>
                    )}

                    <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column' }}>
                        <PlayerList title={teamAName} list={arrTeamA} dropTarget={teamAName} />
                        <PlayerList title={teamBName} list={arrTeamB} dropTarget={teamBName} />
                        <PlayerList title="Unassigned (Drag Bucket)" list={arrUnassigned} dropTarget={null} />
                    </div>
                </Card>
            )}

            {tab === 'courses' && (
                <CoursesTab
                    courses={courses}
                    fetchCourses={fetchCourses}
                    fileRef={fileRef}
                    handleUploadScorecard={handleUploadScorecard}
                    setStatus={setStatus}
                />
            )}

            {tab === 'matchups' && (
                <MatchupsTab
                    courses={courses}
                    players={players}
                    matchups={matchups}
                    fetchMatchups={fetchMatchups}
                    setStatus={setStatus}
                    teamAName={teamAName}
                    teamBName={teamBName}
                />
            )}

            <input
                type="file"
                ref={photoRef}
                style={{ display: 'none' }}
                accept="image/*"
                onChange={handlePhotoChange}
            />
        </div>
    );
}
