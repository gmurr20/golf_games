import React from 'react';
import { Card } from '../components/ui/Card';

export default function Leaderboard() {
    return (
        <div style={{ padding: 'var(--spacing-4)' }}>
            <h1 style={{ marginBottom: 'var(--spacing-4)' }}>Leaderboard</h1>
            <Card className="animate-slide-up">
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border)', paddingBottom: 'var(--spacing-2)' }}>
                    <strong>Team A</strong>
                    <strong style={{color: 'var(--color-accent-win)'}}>2 UP</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 'var(--spacing-2)' }}>
                    <strong>Team B</strong>
                    <span style={{color: 'var(--color-text-light)'}}>2 DOWN</span>
                </div>
            </Card>
        </div>
    );
}
