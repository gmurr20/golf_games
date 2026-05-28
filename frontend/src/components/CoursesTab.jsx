import React, { useState, useRef } from 'react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import backend from '../api/backend';
import './CoursesTab.css';

// ── SCORECARD TABLE RENDERER ──
const ScorecardTable = ({ holes, editable, onChange }) => {
    const splitPoint = holes.length <= 9 ? holes.length : Math.ceil(holes.length / 2);
    const front = holes.filter(h => h.hole_number <= splitPoint);
    const back = holes.filter(h => h.hole_number > splitPoint);

    const frontTotalPar = front.reduce((s, h) => s + Number(h.par), 0);
    const backTotalPar = back.reduce((s, h) => s + Number(h.par), 0);
    const frontTotalYds = front.reduce((s, h) => s + Number(h.yardage || 0), 0);
    const backTotalYds = back.reduce((s, h) => s + Number(h.yardage || 0), 0);

    const renderNine = (nineHoles, label) => (
        <div className="scorecard-nine">
            <table className="scorecard-table">
                <thead>
                    <tr className="scorecard-header-row">
                        <th className="scorecard-label-cell">{label}</th>
                        {nineHoles.map(h => (
                            <th key={h.hole_number} className="scorecard-hole-cell">{h.hole_number}</th>
                        ))}
                        <th className="scorecard-total-cell">TOT</th>
                    </tr>
                </thead>
                <tbody>
                    <tr className="scorecard-par-row">
                        <td className="scorecard-label-cell">Par</td>
                        {nineHoles.map((h, i) => (
                            <td key={h.hole_number} className="scorecard-data-cell">
                                {editable ? (
                                    <input
                                        type="number"
                                        className="scorecard-input"
                                        value={h.par}
                                        onChange={e => onChange(holes.indexOf(h), 'par', e.target.value)}
                                    />
                                ) : (
                                    <span className="scorecard-value">{h.par}</span>
                                )}
                            </td>
                        ))}
                        <td className="scorecard-total-cell scorecard-value-total">
                            {label === 'OUT' ? frontTotalPar : backTotalPar}
                        </td>
                    </tr>
                    <tr className="scorecard-yardage-row">
                        <td className="scorecard-label-cell">Yds</td>
                        {nineHoles.map((h, i) => (
                            <td key={h.hole_number} className="scorecard-data-cell">
                                {editable ? (
                                    <input
                                        type="number"
                                        className="scorecard-input"
                                        value={h.yardage || ''}
                                        placeholder="—"
                                        onChange={e => onChange(holes.indexOf(h), 'yardage', e.target.value)}
                                    />
                                ) : (
                                    <span className="scorecard-value scorecard-yardage">{h.yardage || '—'}</span>
                                )}
                            </td>
                        ))}
                        <td className="scorecard-total-cell scorecard-value-total">
                            {(label === 'OUT' ? frontTotalYds : backTotalYds) || '—'}
                        </td>
                    </tr>
                    <tr className="scorecard-hdcp-row">
                        <td className="scorecard-label-cell">Hdcp</td>
                        {nineHoles.map((h, i) => (
                            <td key={h.hole_number} className="scorecard-data-cell">
                                {editable ? (
                                    <input
                                        type="number"
                                        className="scorecard-input"
                                        value={h.handicap_index}
                                        onChange={e => onChange(holes.indexOf(h), 'handicap_index', e.target.value)}
                                    />
                                ) : (
                                    <span className="scorecard-value scorecard-hdcp">{h.handicap_index}</span>
                                )}
                            </td>
                        ))}
                        <td className="scorecard-total-cell"></td>
                    </tr>
                </tbody>
            </table>
        </div>
    );

    return (
        <div className="scorecard-container">
            {front.length > 0 && renderNine(front, 'OUT')}
            {back.length > 0 && renderNine(back, 'IN')}
            <div className="scorecard-grand-total">
                <span>{holes.length}-Hole Total</span>
                <span className="scorecard-grand-total-value">Par {frontTotalPar + backTotalPar}</span>
                {(frontTotalYds + backTotalYds > 0) && (
                    <span className="scorecard-grand-total-yds">{frontTotalYds + backTotalYds} yds</span>
                )}
            </div>
        </div>
    );
};

export default function CoursesTab({ courses, fetchCourses, fileRef, handleUploadScorecard, setStatus }) {
    const [view, setView] = useState('list'); // 'list' | 'detail' | 'create'
    const [selectedCourse, setSelectedCourse] = useState(null);
    const [selectedTeeIdx, setSelectedTeeIdx] = useState(0);
    const [editMode, setEditMode] = useState(false);
    const [editCourseName, setEditCourseName] = useState('');
    const [editHoles, setEditHoles] = useState([]);
    const [editTee, setEditTee] = useState({});
    const courseLogoRef = useRef(null);

    const [isScanMode, setIsScanMode] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [previews, setPreviews] = useState([]);
    const [scanning, setScanning] = useState(false);
    const [scanStep, setScanStep] = useState(0);

    const SCAN_MESSAGES = [
        "🔍 Preparing images for Gemini...",
        "🚀 Uploading pages to Gemini 3.5 Flash...",
        "🧠 Analyzing scorecard structures...",
        "⛳ Extracting tee ratings and slopes...",
        "📊 Aligning hole pars and yardages...",
        "💾 Saving course data to PostgreSQL..."
    ];

    const handleFilesSelected = (e) => {
        const files = Array.from(e.target.files);
        addFiles(files);
    };

    const handleDragOver = (e) => {
        e.preventDefault();
    };

    const handleDrop = (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        addFiles(files);
    };

    const addFiles = (files) => {
        const valid = files.filter(f => f.type.startsWith('image/') || f.type === 'application/pdf');
        if (valid.length === 0) return;
        
        setSelectedFiles(prev => [...prev, ...valid]);
        
        const newPreviews = valid.map(f => {
            if (f.type === 'application/pdf') {
                return 'https://cdn-icons-png.flaticon.com/512/337/337946.png';
            }
            return URL.createObjectURL(f);
        });
        setPreviews(prev => [...prev, ...newPreviews]);
    };

    const removeFile = (idx) => {
        if (previews[idx] && previews[idx].startsWith('blob:')) {
            URL.revokeObjectURL(previews[idx]);
        }
        setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
        setPreviews(prev => prev.filter((_, i) => i !== idx));
    };

    const cancelScanMode = () => {
        previews.forEach(p => {
            if (p.startsWith('blob:')) URL.revokeObjectURL(p);
        });
        setSelectedFiles([]);
        setPreviews([]);
        setIsScanMode(false);
        setScanning(false);
    };

    const triggerAIScan = async () => {
        if (selectedFiles.length === 0) return;
        setScanning(true);
        setScanStep(0);
        setStatus('Preparing files for AI analysis...');
        
        const interval = setInterval(() => {
            setScanStep(prev => {
                if (prev < SCAN_MESSAGES.length - 1) return prev + 1;
                return prev;
            });
        }, 2800);
        
        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('images', file);
        });
        
        try {
            const res = await backend.post('/courses/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const parsed = res.data;
            
            setScanStep(SCAN_MESSAGES.length - 1);
            
            const saveRes = await backend.post('/courses', {
                name: parsed.course_name || 'Parsed Course',
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
            
            clearInterval(interval);
            
            const newCourseId = saveRes.data.id;
            
            if (parsed.warnings && parsed.warnings.length > 0) {
                const warnMsg = `Success, but with warnings:\n\n${parsed.warnings.join('\n')}\n\nPlease check course ratings.`;
                window.alert(warnMsg);
            }
            
            setStatus(`Success! AI parsed and saved ${parsed.course_name}.`);
            
            previews.forEach(p => {
                if (p.startsWith('blob:')) URL.revokeObjectURL(p);
            });
            setSelectedFiles([]);
            setPreviews([]);
            setIsScanMode(false);
            setScanning(false);
            
            await fetchCourses();
            
            const detailRes = await backend.get(`/courses/${newCourseId}`);
            openDetail(detailRes.data);
            
        } catch (error) {
            clearInterval(interval);
            setScanning(false);
            console.error(error);
            setStatus('Failed to parse scorecard images. Please check Gemini API key configuration.');
        }
    };

    // Manual course creation state
    const [newName, setNewName] = useState('');
    const [newCourseHoles, setNewCourseHoles] = useState(18);
    const [newTees, setNewTees] = useState([createEmptyTee(18)]);

    function createEmptyTee(holesCount = 18) {
        return {
            name: '', rating: 72.0, slope: 113,
            rating_female: '', slope_female: '',
            holes: Array.from({ length: holesCount }, (_, i) => ({
                hole_number: i + 1, par: 4, yardage: '', handicap_index: i + 1
            }))
        };
    }

    const handleHoleCountChange = (e) => {
        const count = parseInt(e.target.value);
        setNewCourseHoles(count);
        setNewTees(prev => prev.map(t => {
            let newHoles = [...t.holes];
            if (count < newHoles.length) {
                newHoles = newHoles.slice(0, count);
            } else if (count > newHoles.length) {
                for (let i = newHoles.length; i < count; i++) {
                    newHoles.push({ hole_number: i + 1, par: 4, yardage: '', handicap_index: i + 1 });
                }
            }
            return { ...t, holes: newHoles };
        }));
    };

    const openDetail = (course) => {
        setSelectedCourse(course);
        setSelectedTeeIdx(0);
        setEditMode(false);
        setView('detail');
    };

    const startEdit = () => {
        setEditCourseName(selectedCourse.name);
        const tee = selectedCourse.tees[selectedTeeIdx];
        if (tee) {
            setEditTee({ 
                name: tee.name, 
                rating: tee.rating, 
                slope: tee.slope, 
                rating_female: tee.rating_female || '', 
                slope_female: tee.slope_female || '',
                par: tee.par 
            });
            setEditHoles(tee.holes.map(h => ({ ...h })));
        }
        setEditMode(true);
    };

    const cancelEdit = () => {
        setEditMode(false);
        setEditCourseName('');
        setEditHoles([]);
        setEditTee({});
    };

    const saveEdit = async () => {
        const tee = selectedCourse.tees[selectedTeeIdx];
        try {
            if (editCourseName !== selectedCourse.name) {
                await backend.put(`/courses/${selectedCourse.id}`, { name: editCourseName });
            }
            
            // Recalculate total par from holes
            const totalPar = editHoles.reduce((sum, h) => sum + Number(h.par), 0);
            await backend.put(`/tees/${tee.id}`, {
                ...editTee,
                rating: Number(editTee.rating),
                slope: Number(editTee.slope),
                rating_female: editTee.rating_female ? Number(editTee.rating_female) : null,
                slope_female: editTee.slope_female ? Number(editTee.slope_female) : null,
                par: totalPar,
                holes: editHoles.map(h => ({
                    id: h.id,
                    par: Number(h.par),
                    yardage: h.yardage ? Number(h.yardage) : null,
                    handicap_index: Number(h.handicap_index)
                }))
            });
            setStatus('Course data saved successfully!');
            setEditMode(false);
            await fetchCourses();
            // Re-fetch the updated course
            const res = await backend.get(`/courses/${selectedCourse.id}`);
            setSelectedCourse(res.data);
        } catch (e) {
            setStatus('Failed to save changes.');
        }
    };

    const handleDeleteCourse = async (courseId) => {
        if (!window.confirm('Delete this entire course? This will also remove any matchups and scores associated with this course.')) return;
        try {
            await backend.delete(`/courses/${courseId}`);
            setStatus('Course deleted.');
            setView('list');
            setSelectedCourse(null);
            fetchCourses();
        } catch (e) {
            setStatus('Failed to delete course.');
        }
    };

    const handleCourseLogoChange = (e) => {
        const file = e.target.files[0];
        if (!file || !selectedCourse) return;
        setStatus('Processing logo...');
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = async () => {
                const canvas = document.createElement('canvas');
                const size = 400;
                canvas.width = size;
                canvas.height = size;
                const ctx = canvas.getContext('2d');
                let srcX = 0, srcY = 0, srcW = img.width, srcH = img.height;
                if (srcW > srcH) { srcX = (srcW - srcH) / 2; srcW = srcH; } 
                else { srcY = (srcH - srcW) / 2; srcH = srcW; }
                ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, size, size);
                const base64 = canvas.toDataURL('image/jpeg', 0.85);
                try {
                    await backend.post(`/courses/${selectedCourse.id}/image`, { logo: base64 });
                    setStatus('Logo updated!');
                    setSelectedCourse(prev => ({ ...prev, logo: base64 }));
                    fetchCourses();
                } catch (err) {
                    setStatus('Failed to upload logo.');
                }
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    };

    const handleCreateCourse = async (e) => {
        e.preventDefault();
        try {
            await backend.post('/courses', {
                name: newName,
                tees: newTees.map(t => ({
                    name: t.name || 'Default',
                    rating: Number(t.rating),
                    slope: Number(t.slope),
                    rating_female: t.rating_female ? Number(t.rating_female) : null,
                    slope_female: t.slope_female ? Number(t.slope_female) : null,
                    par: t.holes.reduce((sum, h) => sum + Number(h.par), 0),
                    holes: t.holes.map(h => ({
                        hole_number: h.hole_number,
                        par: Number(h.par),
                        yardage: h.yardage ? Number(h.yardage) : null,
                        handicap_index: Number(h.handicap_index)
                    }))
                }))
            });
            setStatus(`Successfully created ${newName}!`);
            setNewName('');
            setNewCourseHoles(18);
            setNewTees([createEmptyTee(18)]);
            setView('list');
            fetchCourses();
        } catch (e) {
            setStatus('Failed to create course.');
        }
    };

    const updateNewTeeHole = (teeIdx, holeIdx, field, value) => {
        setNewTees(prev => {
            const copy = prev.map(t => ({ ...t, holes: t.holes.map(h => ({ ...h })) }));
            copy[teeIdx].holes[holeIdx][field] = value;
            return copy;
        });
    };

    const updateNewTeeMeta = (teeIdx, field, value) => {
        setNewTees(prev => {
            const copy = prev.map(t => ({ ...t, holes: t.holes.map(h => ({ ...h })) }));
            copy[teeIdx][field] = value;
            return copy;
        });
    };

    const addNewTee = () => {
        setNewTees(prev => [...prev, createEmptyTee(newCourseHoles)]);
    };

    const removeNewTee = (idx) => {
        if (newTees.length <= 1) return;
        setNewTees(prev => prev.filter((_, i) => i !== idx));
    };

    const updateEditHole = (holeIdx, field, value) => {
        setEditHoles(prev => {
            const copy = prev.map(h => ({ ...h }));
            copy[holeIdx][field] = value;
            return copy;
        });
    };

    // ── CREATE VIEW ──

    // ── CREATE VIEW ──
    if (view === 'create') {
        return (
            <div className="animate-slide-up">
                <div className="courses-header detail-header-sticky">
                    <button className="back-button nav-back" onClick={() => setView('list')}>
                        <span className="back-icon">←</span>
                        <span className="back-text">Courses</span>
                    </button>
                    <h3 className="header-title">Create Course</h3>
                </div>
                <Card style={{ marginTop: '1rem' }}>
                    <form onSubmit={handleCreateCourse}>
                        <div className="create-course-name">
                            <label>Course Name</label>
                            <input
                                type="text"
                                required
                                value={newName}
                                onChange={e => setNewName(e.target.value)}
                                placeholder="e.g. Augusta National"
                                className="course-name-input"
                            />
                        </div>
                        <div className="create-course-name" style={{ marginTop: '1rem' }}>
                            <label>Number of Holes</label>
                            <input
                                type="number"
                                min="1"
                                max="36"
                                value={newCourseHoles}
                                onChange={handleHoleCountChange}
                                className="course-name-input"
                                style={{ width: '100px', display: 'block' }}
                            />
                        </div>

                        {newTees.map((tee, teeIdx) => (
                            <div key={teeIdx} className="create-tee-section">
                                <div className="create-tee-header">
                                    <h4>Tee Set {teeIdx + 1}</h4>
                                    {newTees.length > 1 && (
                                        <button type="button" className="remove-tee-btn" onClick={() => removeNewTee(teeIdx)}>Remove</button>
                                    )}
                                </div>
                                <div className="tee-meta-grid">
                                    <div className="tee-meta-field">
                                        <label>Tee Name</label>
                                        <input type="text" placeholder="e.g. Blue" value={tee.name}
                                            onChange={e => updateNewTeeMeta(teeIdx, 'name', e.target.value)} />
                                    </div>
                                    <div className="tee-meta-field">
                                        <label>Rating</label>
                                        <input type="number" step="0.1" value={tee.rating}
                                            onChange={e => updateNewTeeMeta(teeIdx, 'rating', e.target.value)} />
                                    </div>
                                    <div className="tee-meta-field">
                                        <label>Slope</label>
                                        <input type="number" value={tee.slope}
                                            onChange={e => updateNewTeeMeta(teeIdx, 'slope', e.target.value)} />
                                    </div>
                                    <div className="tee-meta-field">
                                        <label>Women's Rating</label>
                                        <input type="number" step="0.1" value={tee.rating_female}
                                            onChange={e => updateNewTeeMeta(teeIdx, 'rating_female', e.target.value)} placeholder="Optional" />
                                    </div>
                                    <div className="tee-meta-field">
                                        <label>Women's Slope</label>
                                        <input type="number" value={tee.slope_female}
                                            onChange={e => updateNewTeeMeta(teeIdx, 'slope_female', e.target.value)} placeholder="Optional" />
                                    </div>
                                </div>
                                <ScorecardTable
                                    holes={tee.holes}
                                    editable={true}
                                    onChange={(holeIdx, field, value) => updateNewTeeHole(teeIdx, holeIdx, field, value)}
                                />
                            </div>
                        ))}

                        <div className="create-actions">
                            <Button type="button" variant="outline" onClick={addNewTee}>+ Add Another Tee Set</Button>
                            <Button type="submit">Create Course</Button>
                        </div>
                    </form>
                </Card>
            </div>
        );
    }

    // ── DETAIL VIEW ──
    if (view === 'detail' && selectedCourse) {
        const activeTee = selectedCourse.tees[selectedTeeIdx];
        const displayHoles = editMode ? editHoles : (activeTee?.holes || []);

        return (
            <div className="animate-slide-up">
                <div className="courses-header detail-header-sticky">
                    <button className="back-button nav-back" onClick={() => { setView('list'); setEditMode(false); }}>
                        <span className="back-icon">←</span>
                        <span className="back-text-full">Back to Courses</span>
                        <span className="back-text-short">Back</span>
                    </button>
                </div>

                <Card style={{ marginTop: '1rem' }}>
                    <div className="course-detail-header" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div 
                            className="course-logo-container" 
                            style={{ position: 'relative', cursor: 'pointer', flexShrink: 0 }}
                            onClick={() => courseLogoRef.current && courseLogoRef.current.click()}
                        >
                            {selectedCourse.logo ? (
                                <img src={selectedCourse.logo} alt="course logo" style={{ width: '60px', height: '60px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--color-border)' }} />
                            ) : (
                                <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'var(--color-surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', border: '2px dashed var(--color-border)' }}>⛳</div>
                            )}
                            <div style={{ position: 'absolute', bottom: -5, right: -5, background: 'var(--color-primary)', color: 'white', borderRadius: '50%', width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem' }}>📷</div>
                        </div>
                        <div className="course-title-section" style={{ flex: 1 }}>
                            {editMode ? (
                                <input
                                    type="text"
                                    className="course-name-input"
                                    value={editCourseName}
                                    onChange={e => setEditCourseName(e.target.value)}
                                    style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '0.25rem', width: '100%', border: '1px solid var(--color-border)', borderRadius: '4px', padding: '0.25rem' }}
                                />
                            ) : (
                                <h2 className="course-detail-title" style={{ margin: 0 }}>{selectedCourse.name}</h2>
                            )}
                            <p className="course-detail-subtitle" style={{ margin: 0 }}>{selectedCourse.tees.length} tee{selectedCourse.tees.length !== 1 ? 's' : ''} registered</p>
                        </div>
                        <button 
                            className="card-level-delete-btn" 
                            onClick={() => handleDeleteCourse(selectedCourse.id)}
                            title="Delete Course"
                        >
                            ×
                        </button>
                    </div>

                    {/* Tee Selector Buttons (Wrapped) */}
                    {selectedCourse.tees.length > 0 && (
                        <div className="tee-selector">
                            {selectedCourse.tees.map((t, idx) => (
                                <button
                                    key={t.id}
                                    className={`tee-tab ${idx === selectedTeeIdx ? 'tee-tab-active' : ''}`}
                                    onClick={() => { setSelectedTeeIdx(idx); cancelEdit(); }}
                                >
                                    {t.name}
                                </button>
                            ))}
                        </div>
                    )}

                    {activeTee && (
                        <>
                            {/* Tee Metadata */}
                            <div className="tee-meta-display">
                                {editMode ? (
                                    <div className="tee-meta-grid">
                                        <div className="tee-meta-field">
                                            <label>Name</label>
                                            <input type="text" value={editTee.name}
                                                onChange={e => setEditTee(prev => ({ ...prev, name: e.target.value }))} />
                                        </div>
                                        <div className="tee-meta-field">
                                            <label>Rating</label>
                                            <input type="number" step="0.1" value={editTee.rating}
                                                onChange={e => setEditTee(prev => ({ ...prev, rating: parseFloat(e.target.value) }))} />
                                        </div>
                                        <div className="tee-meta-field">
                                            <label>Slope</label>
                                            <input type="number" value={editTee.slope}
                                                onChange={e => setEditTee(prev => ({ ...prev, slope: parseInt(e.target.value) }))} />
                                        </div>
                                        <div className="tee-meta-field">
                                            <label>Women's Rating</label>
                                            <input type="number" step="0.1" value={editTee.rating_female}
                                                onChange={e => setEditTee(prev => ({ ...prev, rating_female: e.target.value }))} placeholder="Optional" />
                                        </div>
                                        <div className="tee-meta-field">
                                            <label>Women's Slope</label>
                                            <input type="number" value={editTee.slope_female}
                                                onChange={e => setEditTee(prev => ({ ...prev, slope_female: e.target.value }))} placeholder="Optional" />
                                        </div>
                                    </div>
                                ) : (
                                    <div className="tee-meta-pills">
                                        <span className="tee-pill">Men: {activeTee.rating}/{activeTee.slope}</span>
                                        {activeTee.rating_female && (
                                            <span className="tee-pill">Women: {activeTee.rating_female}/{activeTee.slope_female}</span>
                                        )}
                                        <span className="tee-pill tee-pill-par">Par {activeTee.par}</span>
                                    </div>
                                )}
                            </div>

                            <ScorecardTable
                                holes={displayHoles}
                                editable={editMode}
                                onChange={updateEditHole}
                            />
                        </>
                    )}

                    {selectedCourse.tees.length === 0 && (
                        <p className="empty-state">No tees have been added to this course yet.</p>
                    )}

                    {/* Edit Actions */}
                    <div className="detail-actions">
                        {editMode ? (
                            <>
                                <Button onClick={saveEdit}>💾 Save Changes</Button>
                                <Button variant="outline" onClick={cancelEdit}>Cancel</Button>
                            </>
                        ) : (
                            <Button variant="outline" onClick={startEdit}>✏️ Edit Course & Hole Data</Button>
                        )}
                    </div>
                    <input 
                        type="file" 
                        ref={courseLogoRef} 
                        style={{ display: 'none' }} 
                        accept="image/*" 
                        onChange={handleCourseLogoChange} 
                    />
                </Card>
            </div>
        );
    }

    // ── LIST VIEW (Default) ──
    return (
        <div className="animate-slide-up">
            {/* Upload & Create Actions */}
            {isScanMode ? (
                <Card style={{ marginBottom: '1rem' }} className="scan-card-expanded">
                    <div className="scan-header-bar">
                        <h3 style={{ margin: 0 }}>📸 AI Scorecard Scan</h3>
                        <span className="scan-sub-label">Gemini 3.5 Flash Ingestion</span>
                    </div>
                    
                    {scanning ? (
                        <div className="scanning-overlay">
                            <div className="pulsing-scan-circle">
                                <span className="scan-icon">⚡</span>
                            </div>
                            <div className="scan-laser-container">
                                <div className="scan-laser-line"></div>
                                <div className="scanning-thumbnails">
                                    {previews.map((src, i) => (
                                        <img key={i} src={src} alt="scanning page" className="scanning-img-tiny" />
                                    ))}
                                </div>
                            </div>
                            <h4 className="scan-progress-title">Ingesting Scorecard</h4>
                            <p className="scan-progress-msg animate-pulse">{SCAN_MESSAGES[scanStep]}</p>
                            <div className="scan-progress-dots">
                                <div className="dot"></div>
                                <div className="dot"></div>
                                <div className="dot"></div>
                            </div>
                        </div>
                    ) : (
                        <>
                            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: '1rem' }}>
                                Drag & drop or select multiple photos of your scorecard (e.g. pages 1 & 2, rules cover page, slope/rating charts).
                            </p>
                            <input 
                                type="file" 
                                ref={fileRef} 
                                accept="image/*,application/pdf" 
                                multiple 
                                onChange={handleFilesSelected} 
                                style={{ display: 'none' }} 
                            />
                            
                            {selectedFiles.length === 0 ? (
                                <div 
                                    className="scan-dropzone glass-card"
                                    onClick={() => fileRef.current.click()}
                                    onDragOver={handleDragOver}
                                    onDrop={handleDrop}
                                >
                                    <div className="scan-dropzone-icon">📥</div>
                                    <h4>Drop scorecard photos here</h4>
                                    <p>or click to browse files (PNG, JPG, PDF)</p>
                                    <span className="scan-dropzone-badge">Multiple pages supported</span>
                                </div>
                            ) : (
                                <div className="scan-previews-container">
                                    <label className="scan-previews-title">Selected Pages ({selectedFiles.length})</label>
                                    <div className="scan-previews-grid">
                                        {previews.map((src, idx) => (
                                            <div key={idx} className="scan-preview-card animate-scale-in glass-card">
                                                <img src={src} alt={`Page ${idx + 1}`} />
                                                <span className="scan-preview-number">Page {idx + 1}</span>
                                                <button 
                                                    type="button" 
                                                    className="scan-preview-delete" 
                                                    onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                                                    title="Remove page"
                                                >
                                                    ×
                                                </button>
                                            </div>
                                        ))}
                                        <button 
                                            type="button" 
                                            className="scan-preview-add-card glass-card" 
                                            onClick={() => fileRef.current.click()}
                                        >
                                            <span className="add-card-icon">+</span>
                                            <span className="add-card-text">Add Page</span>
                                        </button>
                                    </div>
                                </div>
                            )}
                            
                            <div className="scan-actions-row">
                                <Button 
                                    onClick={triggerAIScan} 
                                    disabled={selectedFiles.length === 0} 
                                    style={{ flex: 2 }}
                                >
                                    ✨ Extract with Gemini AI
                                </Button>
                                <Button 
                                    variant="outline" 
                                    onClick={cancelScanMode} 
                                    style={{ flex: 1 }}
                                >
                                    Cancel
                                </Button>
                            </div>
                        </>
                    )}
                </Card>
            ) : (
                <Card style={{ marginBottom: '1rem' }}>
                    <h3 style={{ marginBottom: '0.5rem' }}>Add a Course</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: '1rem' }}>
                        Upload a photo of a scorecard for AI extraction, or enter course data manually.
                    </p>
                    <div className="add-course-actions">
                        <Button onClick={() => setIsScanMode(true)} style={{ flex: 1 }}>
                            📸 AI Scan Scorecard
                        </Button>
                        <Button variant="outline" onClick={() => setView('create')} style={{ flex: 1 }}>
                            ✍️ Add Manually
                        </Button>
                    </div>
                </Card>
            )}

            {/* Course List */}
            <Card>
                <h3 style={{ marginBottom: '1rem' }}>Course Library</h3>
                {courses.length === 0 && (
                    <p className="empty-state">No courses yet. Upload a scorecard or add one manually to get started!</p>
                )}
                <div className="course-grid">
                    {courses.map(c => {
                        const totalPar = c.tees.length > 0 ? c.tees[0].par : '—';
                        const totalYds = c.tees.length > 0 && c.tees[0].holes
                            ? c.tees[0].holes.reduce((s, h) => s + (h.yardage || 0), 0)
                            : 0;
                        return (
                            <button key={c.id} className="course-card" onClick={() => openDetail(c)}>
                                <div className="course-card-icon">
                                    {c.logo ? <img src={c.logo} alt="logo" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} /> : '⛳'}
                                </div>
                                <div className="course-card-info">
                                    <strong className="course-card-name">{c.name}</strong>
                                    <span className="course-card-meta">
                                        {c.tees.length} tee{c.tees.length !== 1 ? 's' : ''}
                                        {totalPar !== '—' && <> · Par {totalPar}</>}
                                        {totalYds > 0 && <> · {totalYds} yds</>}
                                    </span>
                                </div>
                                <span className="course-card-arrow">›</span>
                            </button>
                        );
                    })}
                </div>
            </Card>
        </div>
    );
}
