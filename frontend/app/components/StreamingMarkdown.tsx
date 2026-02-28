'use client';

import { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';

interface StreamingMarkdownProps {
    content: string;
    animate?: boolean;
    speed?: number; // chars per frame
}

export default function StreamingMarkdown({ content, animate = false, speed = 8 }: StreamingMarkdownProps) {
    const [displayedLength, setDisplayedLength] = useState(animate ? 0 : content.length);
    const [isComplete, setIsComplete] = useState(!animate);

    useEffect(() => {
        if (!animate) {
            setDisplayedLength(content.length);
            setIsComplete(true);
            return;
        }

        setDisplayedLength(0);
        setIsComplete(false);

        const interval = setInterval(() => {
            setDisplayedLength(prev => {
                const next = prev + speed;
                if (next >= content.length) {
                    clearInterval(interval);
                    setIsComplete(true);
                    return content.length;
                }
                return next;
            });
        }, 16); // ~60fps

        return () => clearInterval(interval);
    }, [content, animate, speed]);

    const displayedContent = useMemo(
        () => content.slice(0, displayedLength),
        [content, displayedLength]
    );

    return (
        <div className={`markdown-body ${isComplete ? '' : 'streaming'}`}>
            <ReactMarkdown>{displayedContent}</ReactMarkdown>
            {!isComplete && <span className="streaming-cursor">▊</span>}
        </div>
    );
}
