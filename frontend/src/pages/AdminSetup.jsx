import React, { useState, useEffect, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import CoursesTab from '../components/CoursesTab';
import MatchupsTab from '../components/MatchupsTab';
import backend, { setAdminKey } from '../api/backend';

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
            <div style={{ 
                padding: 'var(--spacing-4)', 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                justifyContent: 'center', 
                minHeight: '60vh' 
            }}>
                <Card className="animate-slide-up" style={{ width: '100%', maxWidth: '380px', textAlign: 'center' }}>
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🔒</div>
                    <h2 style={{ margin: '0 0 0.25rem 0', color: 'var(--color-text)' }}>Admin</h2>
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: '1.5rem' }}>Enter the password to continue</p>
                    <form onSubmit={handleLogin} style={{ display: 'grid', gap: 'var(--spacing-3)' }}>
                        <input 
                            type="password" 
                            required 
                            value={password} 
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Password"
                            autoFocus
                            style={{ 
                                width: '100%', 
                                padding: 'var(--spacing-3)', 
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--color-border)',
                                fontSize: '1rem',
                                textAlign: 'center'
                            }} 
                        />
                        <Button type="submit" disabled={loading}>
                            {loading ? 'Unlocking...' : 'Unlock'}
                        </Button>
                    </form>
                    {status && <div style={{marginTop: '1rem', color: 'var(--color-accent-lose)', fontSize: '0.85rem'}}>{status}</div>}
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

    const fetchConfig = async () => {
        try {
            const res = await backend.get('/competitions/settings');
            setTeamAName(res.data.team_a_name);
            setTeamBName(res.data.team_b_name);
        } catch(e) { }
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
                await backend.put(`/players/${editPlayerId}`, {name: pName, handicap_index: parseFloat(pIndex), team: pTeam});
                setStatus(`Updated Player: ${pName}`);
            } else {
                await backend.post('/players', {name: pName, handicap_index: parseFloat(pIndex), team: pTeam});
                setStatus(`Added Player: ${pName}`);
            }
            setEditPlayerId(null);
            setPName(''); setPIndex(''); setPTeam('');
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
    };

    const handleDeleteClick = async (id) => {
        if (!window.confirm("Are you sure you want to delete this player?")) return;
        await backend.delete(`/players/${id}`);
        setStatus('Player deleted.');
        fetchPlayers();
    };

    // AI PROCESSOR
    const handleUploadScorecard = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setStatus('Processing via AI... this may take 15 seconds.');
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
                    par: tee.holes.reduce((a, b) => a + Number(b.par), 0),
                    holes: tee.holes
                }))
            });
            setStatus(`Success! AI Documented ${parsed.course_name} with ${parsed.tees.length} tees.`);
            fetchCourses();
        } catch(error) {
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
            <h4 style={{marginBottom: '0.75rem', color: 'var(--color-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.35rem'}}>
                {title} ({list.length})
            </h4>
            <ul style={{listStyle: 'none', padding: 0, margin: 0}}>
                {list.map(p => (
                    <li 
                        key={p.id} 
                        draggable 
                        onDragStart={(e) => handleDragStart(e, p)}
                        onDragEnd={handleDragEnd}
                        style={{
                            display:'flex', 
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
                        <div style={{display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0}}>
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
                            <strong style={{fontSize: '0.95rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--color-text)'}}>{p.name}</strong>
                        </div>
                        <div style={{display:'flex', gap: '0.5rem', flexShrink: 0}}>
                            <Button variant="outline" style={{padding: '0.25rem 0.5rem', fontSize: '0.75rem'}} onClick={() => handleEditClick(p)}>✏️</Button>
                            <Button variant="outline" style={{padding: '0.25rem 0.5rem', fontSize: '0.75rem', borderColor: 'var(--color-accent-lose)', color: 'var(--color-accent-lose)'}} onClick={() => handleDeleteClick(p.id)}>X</Button>
                        </div>
                    </li>
                ))}
                {list.length === 0 && <p style={{fontSize: '0.8rem', color: 'var(--color-text-light)', fontStyle:'italic', textAlign: 'center', padding: '1rem 0'}}>Drag players here...</p>}
            </ul>
        </div>
    );

    return (
        <div style={{ padding: 'var(--spacing-4)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
                <h1 style={{ margin: 0 }}>Dashboard</h1>
                <Button variant="outline" onClick={handleLogout} style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}>Log Out</Button>
            </div>
            
            <div style={{display: 'flex', gap: '8px', marginBottom: 'var(--spacing-4)', overflowX: 'auto'}}>
                <Button variant={tab === 'players' ? 'primary' : 'outline'} onClick={() => setTab('players')}>Players</Button>
                <Button variant={tab === 'courses' ? 'primary' : 'outline'} onClick={() => setTab('courses')}>Courses</Button>
                <Button variant={tab === 'matchups' ? 'primary' : 'outline'} onClick={() => setTab('matchups')}>Matchups</Button>
            </div>
            
            {status && <div style={{padding: '12px', background: 'white', borderRadius: '8px', marginBottom: '16px', color: 'var(--color-primary-dark)', borderLeft: '4px solid var(--color-primary)'}}>{status}</div>}

            {tab === 'players' && (
                <Card className="animate-slide-up">
                    <h3 style={{color: editPlayerId ? 'var(--color-accent-win)' : 'var(--color-text)'}}>
                        {editPlayerId ? '✏️ Editing Player' : '➕ Add Player'}
                    </h3>
                    <form onSubmit={handleAddOrEditPlayer} style={{ display: 'grid', gap: '1rem', marginTop: '1rem', marginBottom: '2rem' }}>
                        <input type="text" placeholder="Name" value={pName} onChange={e=>setPName(e.target.value)} style={{padding: '8px', borderRadius: 'var(--radius-sm)'}} required/>
                        <div style={{display: 'flex', gap: '1rem'}}>
                            <input type="number" step="0.1" placeholder="Handicap Index" value={pIndex} onChange={e=>setPIndex(e.target.value)} style={{padding: '8px', borderRadius: 'var(--radius-sm)', flex: 1}} required/>
                            <select value={pTeam} onChange={e=>setPTeam(e.target.value)} style={{padding: '8px', borderRadius: 'var(--radius-sm)', flex: 1}}>
                                <option value="">No Team</option>
                                <option value={teamAName}>{teamAName}</option>
                                <option value={teamBName}>{teamBName}</option>
                            </select>
                        </div>
                        <div style={{display: 'flex', gap: '0.5rem'}}>
                            <Button type="submit" style={{flex: 1}}>{editPlayerId ? 'Save Changes' : 'Create Player'}</Button>
                            {editPlayerId && <Button variant="outline" onClick={()=>{setEditPlayerId(null); setPName(''); setPIndex(''); setPTeam('');}}>Cancel</Button>}
                        </div>
                    </form>
                    
                    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
                        <h3 style={{margin: 0}}>Roster Builder</h3>
                        <Button variant="outline" style={{fontSize: '0.75rem', padding: '0.25rem 0.5rem'}} onClick={() => setIsEditingTeams(!isEditingTeams)}>
                            {isEditingTeams ? 'Cancel Config' : '⚙️ Rename Teams'}
                        </Button>
                    </div>

                    {isEditingTeams && (
                        <div style={{display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', background: 'rgba(0,0,0,0.02)', padding: '1rem', borderRadius: '8px'}}>
                            <input type="text" value={teamAName} onChange={e=>setTeamAName(e.target.value)} style={{padding: '8px', flex: 1, borderRadius: '4px'}} placeholder="Team 1 Name"/>
                            <input type="text" value={teamBName} onChange={e=>setTeamBName(e.target.value)} style={{padding: '8px', flex: 1, borderRadius: '4px'}} placeholder="Team 2 Name"/>
                            <Button onClick={saveTeamConfig}>Save</Button>
                        </div>
                    )}

                    <div style={{marginTop: '1rem', display: 'flex', flexDirection: 'column'}}>
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
        </div>
    );
}
