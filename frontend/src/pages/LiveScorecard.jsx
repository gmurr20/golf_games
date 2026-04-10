import React, { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

export default function LiveScorecard() {
    const [score, setScore] = useState(4); // default par 4
    return (
        <div style={{ padding: 'var(--spacing-4)' }}>
            <h1 style={{ marginBottom: 'var(--spacing-2)' }}>Hole 1</h1>
            <p style={{ color: 'var(--color-text-light)', marginBottom: 'var(--spacing-4)' }}>Par 4 • Handicap 12</p>

            <Card className="animate-slide-up" style={{ textAlign: 'center' }}>
                <h2 style={{ fontSize: '3rem', margin: 'var(--spacing-4) 0' }}>{score}</h2>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--spacing-4)' }}>
                    <Button variant="outline" onClick={() => setScore(s => Math.max(1, s - 1))}>-1</Button>
                    <Button onClick={() => setScore(s => s + 1)}>+1</Button>
                </div>
                <Button className="animate-slide-up" style={{ width: '100%', marginTop: 'var(--spacing-6)' }}>Submit Score</Button>
            </Card>
        </div>
    );
}
