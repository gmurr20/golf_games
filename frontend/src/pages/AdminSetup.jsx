import React from 'react';
import { Card } from '../components/ui/Card';

export default function AdminSetup() {
    return (
        <div style={{ padding: 'var(--spacing-4)' }}>
            <h1 style={{ marginBottom: 'var(--spacing-4)' }}>Admin Setup</h1>
            <Card className="animate-slide-up">
                <h3>Create Competition</h3>
                {/* Real input form goes here */}
                <p style={{color: 'var(--color-text-light)'}}>Coming soon...</p>
            </Card>
        </div>
    );
}
