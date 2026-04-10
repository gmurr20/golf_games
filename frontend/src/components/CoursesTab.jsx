import React, { useState } from 'react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import backend from '../api/backend';
import './CoursesTab.css';

export default function CoursesTab({ courses, fetchCourses, fileRef, handleUploadScorecard, setStatus }) {
    const [view, setView] = useState('list'); // 'list' | 'detail' | 'create'
    const [selectedCourse, setSelectedCourse] = useState(null);
    const [selectedTeeIdx, setSelectedTeeIdx] = useState(0);
    const [editMode, setEditMode] = useState(false);
    const [editHoles, setEditHoles] = useState([]);
    const [editTee, setEditTee] = useState({});

    // Manual course creation state
    const [newName, setNewName] = useState('');
    const [newTees, setNewTees] = useState([createEmptyTee()]);

    function createEmptyTee() {
        return {
            name: '', rating: 72.0, slope: 113,
            holes: Array.from({ length: 18 }, (_, i) => ({
                hole_number: i + 1, par: 4, yardage: '', handicap_index: i + 1
            }))
        };
    }

    const openDetail = (course) => {
        setSelectedCourse(course);
        setSelectedTeeIdx(0);
        setEditMode(false);
        setView('detail');
    };

    const startEdit = () => {
        const tee = selectedCourse.tees[selectedTeeIdx];
        setEditTee({ name: tee.name, rating: tee.rating, slope: tee.slope, par: tee.par });
        setEditHoles(tee.holes.map(h => ({ ...h })));
        setEditMode(true);
    };

    const cancelEdit = () => {
        setEditMode(false);
        setEditHoles([]);
        setEditTee({});
    };

    const saveEdit = async () => {
        const tee = selectedCourse.tees[selectedTeeIdx];
        try {
            // Recalculate total par from holes
            const totalPar = editHoles.reduce((sum, h) => sum + Number(h.par), 0);
            await backend.put(`/tees/${tee.id}`, {
                ...editTee,
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

    const handleCreateCourse = async (e) => {
        e.preventDefault();
        try {
            await backend.post('/courses', {
                name: newName,
                tees: newTees.map(t => ({
                    name: t.name || 'Default',
                    rating: Number(t.rating),
                    slope: Number(t.slope),
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
            setNewTees([createEmptyTee()]);
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
        setNewTees(prev => [...prev, createEmptyTee()]);
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

    // ── SCORECARD TABLE RENDERER ──
    const ScorecardTable = ({ holes, editable, onChange }) => {
        const front = holes.filter(h => h.hole_number <= 9);
        const back = holes.filter(h => h.hole_number > 9);

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
                {renderNine(front, 'OUT')}
                {renderNine(back, 'IN')}
                <div className="scorecard-grand-total">
                    <span>18-Hole Total</span>
                    <span className="scorecard-grand-total-value">Par {frontTotalPar + backTotalPar}</span>
                    {(frontTotalYds + backTotalYds > 0) && (
                        <span className="scorecard-grand-total-yds">{frontTotalYds + backTotalYds} yds</span>
                    )}
                </div>
            </div>
        );
    };

    // ── CREATE VIEW ──
    if (view === 'create') {
        return (
            <div className="animate-slide-up">
                <div className="courses-header">
                    <button className="back-button" onClick={() => setView('list')}>
                        ← Back to Courses
                    </button>
                    <h3 style={{ margin: 0 }}>Create Course Manually</h3>
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
                <div className="courses-header">
                    <button className="back-button" onClick={() => { setView('list'); setEditMode(false); }}>
                        ← Back to Courses
                    </button>
                    <button className="delete-course-btn" onClick={() => handleDeleteCourse(selectedCourse.id)}>
                        🗑 Delete Course
                    </button>
                </div>

                <Card style={{ marginTop: '1rem' }}>
                    <div className="course-detail-header">
                        <div>
                            <h2 className="course-detail-title">{selectedCourse.name}</h2>
                            <p className="course-detail-subtitle">{selectedCourse.tees.length} tee{selectedCourse.tees.length !== 1 ? 's' : ''} registered</p>
                        </div>
                    </div>

                    {/* Tee Selector Tabs */}
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
                                    </div>
                                ) : (
                                    <div className="tee-meta-pills">
                                        <span className="tee-pill">Rating: {activeTee.rating}</span>
                                        <span className="tee-pill">Slope: {activeTee.slope}</span>
                                        <span className="tee-pill tee-pill-par">Par {activeTee.par}</span>
                                    </div>
                                )}
                            </div>

                            {/* Hole-by-Hole Scorecard */}
                            <ScorecardTable
                                holes={displayHoles}
                                editable={editMode}
                                onChange={updateEditHole}
                            />

                            {/* Edit Actions */}
                            <div className="detail-actions">
                                {editMode ? (
                                    <>
                                        <Button onClick={saveEdit}>💾 Save Changes</Button>
                                        <Button variant="outline" onClick={cancelEdit}>Cancel</Button>
                                    </>
                                ) : (
                                    <Button variant="outline" onClick={startEdit}>✏️ Edit Hole Data</Button>
                                )}
                            </div>
                        </>
                    )}

                    {selectedCourse.tees.length === 0 && (
                        <p className="empty-state">No tees have been added to this course yet.</p>
                    )}
                </Card>
            </div>
        );
    }

    // ── LIST VIEW (Default) ──
    return (
        <div className="animate-slide-up">
            {/* Upload & Create Actions */}
            <Card style={{ marginBottom: '1rem' }}>
                <h3 style={{ marginBottom: '0.5rem' }}>Add a Course</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-light)', marginBottom: '1rem' }}>
                    Upload a photo of a scorecard for AI extraction, or enter course data manually.
                </p>
                <div className="add-course-actions">
                    <input type="file" ref={fileRef} accept="image/*,application/pdf" onChange={handleUploadScorecard} style={{ display: 'none' }} />
                    <Button onClick={() => fileRef.current.click()} style={{ flex: 1 }}>
                        📸 AI Scan Scorecard
                    </Button>
                    <Button variant="outline" onClick={() => setView('create')} style={{ flex: 1 }}>
                        ✍️ Add Manually
                    </Button>
                </div>
            </Card>

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
                                <div className="course-card-icon">⛳</div>
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
