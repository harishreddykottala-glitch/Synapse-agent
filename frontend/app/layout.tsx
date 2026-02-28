import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Synapse Agent — AI That Thinks, Plans & Delivers',
    description: 'Autonomous AI agent that accepts natural language goals, decomposes them into execution plans, and delivers real outcomes.',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>
                <div className="app-container">
                    {children}
                </div>
            </body>
        </html>
    );
}
