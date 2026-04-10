import React from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

export default function Home() {
    return (
        <div style={{ padding: 'var(--spacing-4)' }}>
            <h1 style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-primary)' }}>Golf Competition</h1>
            
            <Card className="animate-slide-up">
                <h2>Welcome to the Match!</h2>
                <p style={{ color: 'var(--color-text-light)', marginBottom: 'var(--spacing-4)' }}>Select your profile to start inputting scores.</p>
                <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
                    <Button>Select Profile</Button>
                    <Button variant="outline">View Leaderboard</Button>
                </div>
            </Card>
        </div>
    );
}
