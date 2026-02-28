'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import StreamingMarkdown from './components/StreamingMarkdown';

/* ═══════════════════════════════════════
   Types
   ═══════════════════════════════════════ */

interface Message {
    role: 'user' | 'agent' | 'system';
    content: string;
    timestamp: number;
}

interface PlanStep {
    id: number;
    action: string;
    tool: string;
    status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped';
    output?: string;
}

interface AgentPhase {
    name: string;
    icon: string;
    status: 'idle' | 'active' | 'completed';
}

interface GoalState {
    goalId: string;
    status: string;
    interpretation: any;
    planTitle: string;
    steps: PlanStep[];
    finalReport: string;
    stepsCompleted: number;
    adaptations: number;
}

interface HistoryItem {
    id: string;
    goal: string;
    status: string;
    created_at: string;
    adaptation_count: number;
}

/* ═══════════════════════════════════════
   Example Goals
   ═══════════════════════════════════════ */

const EXAMPLE_GOALS = [
    "Plan my complete study schedule for the GATE examination in 3 months",
    "Build me a personalised fitness and nutrition plan for 30 days",
    "Analyse my startup's task backlog and prioritise by urgency and impact",
    "Help me invest Rs. 10,000 smartly based on current market trends",
];

/* ═══════════════════════════════════════
   Slow Streaming Text Component (for Reasoning Logs) 
   ═══════════════════════════════════════ */
export function SlowStreamingText({ text, active }: { text: string, active: boolean }) {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        if (!active) {
            setDisplayedText(text);
            return;
        }

        let currentIndex = 0;
        setDisplayedText('');

        const interval = setInterval(() => {
            if (currentIndex < text.length) {
                setDisplayedText(text.slice(0, currentIndex + 1));
                currentIndex++;
            } else {
                clearInterval(interval);
            }
        }, 45); // 45ms per character gives a slower, more deliberate "thinking" pace

        return () => clearInterval(interval);
    }, [text, active]);

    return (
        <span>
            {displayedText}
            {active && displayedText.length < text.length && <span className="streaming-cursor"></span>}
        </span>
    );
}

/* ═══════════════════════════════════════
   Main Page Component
   ═══════════════════════════════════════ */

export default function Home() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [goalState, setGoalState] = useState<GoalState | null>(null);
    const [phases, setPhases] = useState<AgentPhase[]>([
        { name: 'Think', icon: '🧠', status: 'idle' },
        { name: 'Plan', icon: '📋', status: 'idle' },
        { name: 'Execute', icon: '⚡', status: 'idle' },
        { name: 'Verify', icon: '🔍', status: 'idle' },
        { name: 'Adapt', icon: '🔄', status: 'idle' },
    ]);
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [activeGoalId, setActiveGoalId] = useState<string | null>(null);
    const [isHistoryOpen, setIsHistoryOpen] = useState(true);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const chatContainerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Fetch chat history on mount
    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/goals');
            if (res.ok) {
                const data = await res.json();
                setHistory(data.goals || []);
            }
        } catch { /* backend not running */ }
    };

    // Auto-scroll messages
    const scrollToBottom = useCallback(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, goalState, scrollToBottom]);

    // WebSocket connection
    const connectWS = useCallback(() => {
        const socket = new WebSocket('ws://localhost:8000/ws');

        socket.onopen = () => {
            console.log('WebSocket connected');
            setWs(socket);
        };

        socket.onmessage = (event) => {
            const { event: eventName, data } = JSON.parse(event.data);
            handleAgentEvent(eventName, data);
        };

        socket.onclose = () => {
            console.log('WebSocket disconnected');
            setWs(null);
            // Reconnect after 3s
            setTimeout(connectWS, 3000);
        };

        socket.onerror = () => {
            socket.close();
        };

        return socket;
    }, []);

    useEffect(() => {
        const socket = connectWS();
        return () => {
            // Prevent the reconnect loop from firing when React unmounts
            socket.onclose = null;
            socket.close();
        };
    }, [connectWS]);

    // Handle agent events from WebSocket
    const handleAgentEvent = (event: string, data: any) => {
        switch (event) {
            case 'started':
                setGoalState({
                    goalId: data.goal_id || '',
                    status: 'started',
                    interpretation: null,
                    planTitle: '',
                    steps: [],
                    finalReport: '',
                    stepsCompleted: 0,
                    adaptations: 0,
                });
                break;

            case 'thinking':
                updatePhase('Think', 'active');
                addSystemMessage(`[Internal] Analyzing objective complexity and routing to cognitive subsystems...`);
                break;

            case 'thought_complete':
                updatePhase('Think', 'completed');
                setGoalState(prev => prev ? { ...prev, interpretation: data.interpretation } : prev);
                const domain = data.interpretation?.domain || 'general';
                const complexity = data.interpretation?.complexity || 'unknown';
                const entities = data.interpretation?.key_entities?.join(', ') || 'none';

                addSystemMessage(`[Analysis Complete] Domain identified: ${domain} | Difficulty: ${complexity}. Key entities detected: [${entities}]`);
                break;

            case 'planning':
                updatePhase('Plan', 'active');
                addSystemMessage(`[Planner Engine] Decomposing objective into sequential executable nodes...`);
                break;

            case 'plan_complete':
                updatePhase('Plan', 'completed');
                const planSteps: PlanStep[] = (data.steps || []).map((s: any) => ({
                    id: s.id,
                    action: s.action,
                    tool: s.tool,
                    status: 'pending' as const,
                }));
                setGoalState(prev => prev ? {
                    ...prev,
                    planTitle: data.plan_title || 'Execution Plan',
                    steps: planSteps,
                } : prev);
                addSystemMessage(`[Plan Generated] Compiled ${data.total_steps || planSteps.length} discrete operations under strategy: "${data.plan_title}"`);
                break;

            case 'executing_step':
                updatePhase('Execute', 'active');
                addSystemMessage(`[Executor] Launching step ${data.step_id || ''}: ${data.action} using tool > ${data.tool}`);
                setGoalState(prev => {
                    if (!prev) return prev;
                    const steps = prev.steps.map(s =>
                        s.id === data.step_id ? { ...s, status: 'running' as const } : s
                    );
                    return { ...prev, steps, status: 'executing' };
                });
                break;

            case 'verifying_step':
                updatePhase('Verify', 'active');
                addSystemMessage(`[Verifier] Reviewing step constraints and output validity...`);
                break;

            case 'step_passed':
                updatePhase('Verify', 'completed');
                updatePhase('Execute', 'active');
                setGoalState(prev => {
                    if (!prev) return prev;
                    const steps = prev.steps.map(s =>
                        s.id === data.step_id ? { ...s, status: 'passed' as const } : s
                    );
                    return { ...prev, steps, stepsCompleted: prev.stepsCompleted + 1 };
                });
                break;

            case 'step_failed':
                setGoalState(prev => {
                    if (!prev) return prev;
                    const steps = prev.steps.map(s =>
                        s.id === data.step_id ? { ...s, status: 'failed' as const } : s
                    );
                    return { ...prev, steps };
                });
                addSystemMessage(`⚠️ Step failed: ${data.reason?.substring(0, 80)}`);
                break;

            case 'adapting':
                updatePhase('Adapt', 'active');
                addSystemMessage(`🔄 Adapting plan (attempt ${data.adaptation_number})...`);
                break;

            case 'plan_revised':
                updatePhase('Adapt', 'completed');
                setGoalState(prev => prev ? {
                    ...prev,
                    adaptations: prev.adaptations + 1,
                } : prev);
                addSystemMessage(`✅ Plan revised — ${data.new_total_steps} steps, resuming`);
                break;

            case 'completed':
                resetPhases('completed');
                setIsLoading(false);
                setGoalState(prev => prev ? {
                    ...prev,
                    status: 'completed',
                    finalReport: data.final_report || '',
                    stepsCompleted: data.steps_completed || 0,
                    adaptations: data.adaptations || 0,
                } : prev);
                addAgentMessage(data.final_report || 'Goal completed successfully!');
                fetchHistory(); // Refresh history
                break;

            case 'failed':
                setIsLoading(false);
                addSystemMessage(`❌ Agent failed: ${data.error}`);
                break;
        }
    };

    // Phase state helpers
    const updatePhase = (name: string, status: AgentPhase['status']) => {
        setPhases(prev => prev.map(p =>
            p.name === name ? { ...p, status } : p
        ));
    };

    const resetPhases = (status: AgentPhase['status']) => {
        setPhases(prev => prev.map(p => ({ ...p, status })));
    };

    // Message helpers
    const addSystemMessage = (content: string) => {
        setMessages(prev => [...prev, { role: 'system', content, timestamp: Date.now() }]);
    };

    const addAgentMessage = (content: string) => {
        setMessages(prev => [...prev, { role: 'agent', content, timestamp: Date.now() }]);
    };

    // Submit goal
    const handleSubmit = async (goalText?: string) => {
        const text = goalText || input.trim();
        if (!text || isLoading) return;

        setInput('');
        setIsLoading(true);

        // If there's an active goal and it hasn't failed, we might want to treat this as a follow-up
        // But since the current backend explicitly uses AutonomousAgent per goal, we let the UI
        // retain previous messages for visual context rather than wiping them blank every time.
        // We do NOT call `setMessages([])` unconditionally anymore.
        setMessages(prev => [...prev, { role: 'user', content: text, timestamp: Date.now() }]);

        // Reset phases for the *new* cognitive cycle
        setPhases(prev => prev.map(p => ({ ...p, status: 'idle' })));

        if (ws && ws.readyState === WebSocket.OPEN) {
            // The `messages` ref matches the history prior to submit. We just want user and agent logs, not system thought traces
            const contextHistory = messages.filter(m => m.role === 'user' || m.role === 'agent');
            ws.send(JSON.stringify({ type: 'goal', content: text, history: contextHistory }));
        } else {
            // Fallback: use REST API
            try {
                const res = await fetch('/api/goals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ goal: text }),
                });
                const data = await res.json();
                addSystemMessage(`Goal accepted (ID: ${data.goal_id}). Tracking progress...`);
                pollGoalStatus(data.goal_id);
            } catch (err) {
                setIsLoading(false);
                addSystemMessage('❌ Failed to connect to agent. Is the backend running?');
            }
        }
    };

    // Poll goal status (REST API fallback)
    const pollGoalStatus = async (goalId: string) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/goals/${goalId}`);
                const data = await res.json();
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(interval);
                    setIsLoading(false);
                    if (data.final_outcome?.final_report) {
                        addAgentMessage(data.final_outcome.final_report);
                    }
                }
            } catch {
                clearInterval(interval);
                setIsLoading(false);
            }
        }, 2000);
    };

    // Load a past goal from history
    const loadGoal = async (goalId: string) => {
        try {
            const res = await fetch(`http://localhost:8000/api/goals/${goalId}`);
            if (!res.ok) return;
            const data = await res.json();

            setActiveGoalId(goalId);
            setIsLoading(false);

            // Build messages from the goal data
            const loadedMessages: Message[] = [];
            loadedMessages.push({ role: 'user', content: data.goal, timestamp: Date.now() });

            if (data.interpretation) {
                loadedMessages.push({
                    role: 'system',
                    content: `✅ Goal understood — Domain: ${data.interpretation?.domain || 'general'}`,
                    timestamp: Date.now(),
                });
            }
            if (data.plan?.plan_title) {
                loadedMessages.push({
                    role: 'system',
                    content: `✅ Plan: "${data.plan.plan_title}" (${data.plan.steps?.length || 0} steps)`,
                    timestamp: Date.now(),
                });
            }
            if (data.final_outcome?.final_report) {
                loadedMessages.push({
                    role: 'agent',
                    content: data.final_outcome.final_report,
                    timestamp: Date.now(),
                });
            }

            setMessages(loadedMessages);

            // Build plan steps
            const steps: PlanStep[] = (data.plan?.steps || []).map((s: any, i: number) => {
                const result = data.step_results?.find((r: any) => r.step_id === s.id);
                return {
                    id: s.id,
                    action: s.action,
                    tool: s.tool,
                    status: result?.status === 'completed' ? 'passed' as const
                        : result?.status === 'failed' ? 'failed' as const
                            : 'pending' as const,
                };
            });

            setGoalState({
                goalId: data.goal_id,
                status: data.status,
                interpretation: data.interpretation,
                planTitle: data.plan?.plan_title || '',
                steps,
                finalReport: data.final_outcome?.final_report || '',
                stepsCompleted: steps.filter(s => s.status === 'passed').length,
                adaptations: data.adaptation_count || 0,
            });

            // Set phases based on status
            const allDone = data.status === 'completed' || data.status === 'failed';
            setPhases([
                { name: 'Think', icon: '🧠', status: allDone ? 'completed' : 'idle' },
                { name: 'Plan', icon: '📋', status: allDone ? 'completed' : 'idle' },
                { name: 'Execute', icon: '⚡', status: allDone ? 'completed' : 'idle' },
                { name: 'Verify', icon: '🔍', status: allDone ? 'completed' : 'idle' },
                { name: 'Adapt', icon: '🔄', status: allDone ? 'completed' : 'idle' },
            ]);
        } catch (err) {
            console.error('Failed to load goal:', err);
        }
    };

    // Start a new chat
    const startNewChat = () => {
        setMessages([]);
        setGoalState(null);
        setActiveGoalId(null);
        setIsLoading(false);
        setPhases(prev => prev.map(p => ({ ...p, status: 'idle' })));
        inputRef.current?.focus();
    };

    const clearChat = () => {
        if (confirm('Are you sure you want to clear the current chat and start a new context?')) {
            startNewChat();
        }
    };

    // Format time
    const formatTime = (ts?: string | number) => {
        if (!ts) return '';
        try {
            const d = new Date(ts);
            const now = new Date();
            const diffMs = now.getTime() - d.getTime();
            const diffMin = Math.floor(diffMs / 60000);
            if (diffMin < 1) return 'just now';
            if (diffMin < 60) return `${diffMin}m ago`;
            const diffHr = Math.floor(diffMin / 60);
            if (diffHr < 24) return `${diffHr}h ago`;
            return d.toLocaleDateString();
        } catch { return ''; }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <>
            {/* Header */}
            <header className="header">
                <div className="header-brand">
                    <div className="header-logo">S</div>
                    <div>
                        <div className="header-title">Synapse Agent</div>
                        <div className="header-subtitle">Think · Plan · Deliver</div>
                    </div>
                </div>
                <div className="header-status">
                    <span className="dot"></span>
                    <span>{isLoading ? 'Working...' : 'Ready'}</span>
                </div>
            </header>

            {/* Main Content */}
            <main className={`main-content ${!isHistoryOpen ? 'hide-history' : ''}`}>

                {/* Collapsed Sidebar Toggle Button (Shows when history is hidden) */}
                {!isHistoryOpen && (
                    <button
                        className="sidebar-toggle-collapsed"
                        onClick={() => setIsHistoryOpen(true)}
                        title="Show History"
                    >
                        ▶
                    </button>
                )}

                {/* History Sidebar */}
                <div className="history-panel">
                    <div className="history-header">
                        <div className="history-header-left">
                            <span className="history-header-title">History</span>
                            <button
                                className="sidebar-close-btn"
                                onClick={() => setIsHistoryOpen(false)}
                                title="Hide History"
                            >
                                ◀
                            </button>
                        </div>
                        <div className="history-header-actions" style={{ display: 'flex', gap: '8px' }}>
                            <button className="new-chat-btn" onClick={clearChat} title="Clear Current Chat Context" style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>
                                🗑️ Clear
                            </button>
                            <button className="new-chat-btn" onClick={startNewChat}>
                                ＋ New
                            </button>
                        </div>
                    </div>
                    <div className="history-list">
                        {history.length === 0 ? (
                            <div className="history-empty">
                                <div className="history-empty-icon">📭</div>
                                <span>No goals yet</span>
                            </div>
                        ) : (
                            history.map((item) => (
                                <div
                                    key={item.id}
                                    className={`history-item ${activeGoalId === item.id ? 'active' : ''}`}
                                    onClick={() => loadGoal(item.id)}
                                >
                                    <span className="history-item-icon">
                                        {item.status === 'completed' ? '✅' : item.status === 'failed' ? '❌' : '⏳'}
                                    </span>
                                    <div className="history-item-body">
                                        <div className="history-item-goal">{item.goal}</div>
                                        <div className="history-item-meta">
                                            <span className={`history-status-dot ${item.status}`}></span>
                                            <span>{item.status}</span>
                                            <span>·</span>
                                            <span>{formatTime(item.created_at)}</span>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Chat Panel */}
                <div className="chat-panel">
                    <div className="chat-messages" ref={chatContainerRef}>
                        {messages.length === 0 ? (
                            <div className="chat-empty">
                                <div className="chat-empty-icon">
                                    <div className="header-logo">S</div>
                                </div>
                                <h2>How can I help you today?</h2>
                                <p>
                                    I am Synapse, your autonomous AI agent. Tell me your objective, and I will think, plan, execute, and verify until the task is complete.
                                </p>
                                <div className="chat-examples">
                                    {EXAMPLE_GOALS.map((goal, i) => (
                                        <button
                                            key={i}
                                            className="chat-example-btn"
                                            onClick={() => handleSubmit(goal)}
                                        >
                                            {goal}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <>
                                {messages.reduce((acc: any[], msg, i) => {
                                    if (msg.role === 'system') {
                                        const last = acc[acc.length - 1];
                                        if (last && last.type === 'system-group') {
                                            last.messages.push(msg);
                                        } else {
                                            acc.push({ type: 'system-group', id: `sys-group-${i}`, messages: [msg] });
                                        }
                                    } else {
                                        acc.push({ type: 'single', id: `msg-${i}`, message: msg, index: i });
                                    }
                                    return acc;
                                }, []).map((group: any) => {
                                    if (group.type === 'system-group') {
                                        return (
                                            <div key={group.id} className="reasoning-block">
                                                <details open>
                                                    <summary className="reasoning-summary">
                                                        <span className="reasoning-icon">🧠</span> Thought Process
                                                    </summary>
                                                    <div className="reasoning-content">
                                                        {group.messages.map((sysMsg: any, j: number) => {
                                                            // Only animate the very last reasoning step if the agent is still loading
                                                            const isAbsoluteLastMessage = sysMsg === messages[messages.length - 1];
                                                            const isActivelyStreaming = isAbsoluteLastMessage && isLoading;

                                                            return (
                                                                <div key={j} className="reasoning-step">
                                                                    <span className="reasoning-timestamp">{formatTime(sysMsg.timestamp)}</span>
                                                                    <span className="reasoning-text">
                                                                        <SlowStreamingText text={sysMsg.content} active={isActivelyStreaming} />
                                                                    </span>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </details>
                                            </div>
                                        );
                                    } else {
                                        const msg = group.message;
                                        const i = group.index;
                                        return (
                                            <div key={group.id} className={`message ${msg.role}`}>
                                                <div className={`message-avatar ${msg.role === 'user' ? 'user' : 'agent'}`}>
                                                    {msg.role === 'user' ? 'U' : (
                                                        <div className="header-logo" style={{ width: '100%', height: '100%', fontSize: '12px' }}>S</div>
                                                    )}
                                                </div>
                                                <div className="message-body">
                                                    <div className="message-name">{msg.role === 'user' ? 'You' : 'Synapse'}</div>
                                                    <div className="message-content">
                                                        {msg.role === 'agent' ? (
                                                            <StreamingMarkdown
                                                                content={msg.content}
                                                                animate={i === messages.length - 1 && isLoading === false}
                                                            />
                                                        ) : (
                                                            msg.content
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    }
                                })}
                                {isLoading && (
                                    <div className="message agent">
                                        <div className="message-avatar agent">
                                            <div className="header-logo" style={{ width: '100%', height: '100%', fontSize: '12px' }}>S</div>
                                        </div>
                                        <div className="message-body">
                                            <div className="message-name">Synapse</div>
                                            <div className="message-content">
                                                <span className="spinner"></span> Working on your request...
                                            </div>
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </>
                        )}
                    </div>

                    {/* Chat Input */}
                    <div className="chat-input-area">
                        <div className="chat-input-wrapper">
                            <textarea
                                ref={inputRef}
                                className="chat-input"
                                placeholder="Type your goal... (e.g., Plan my GATE study schedule)"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                rows={1}
                                disabled={isLoading}
                            />
                            <button
                                className="chat-send-btn"
                                onClick={() => handleSubmit()}
                                disabled={!input.trim() || isLoading}
                            >
                                {isLoading ? '...' : 'Send'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Dashboard Panel */}
                <div className="dashboard-panel">
                    {/* Agent Status */}
                    <div className="dashboard-section">
                        <div className="dashboard-section-title">Agent Pipeline</div>
                        <div className="agent-status-grid">
                            {phases.map((phase) => (
                                <div key={phase.name} className={`agent-status-item ${phase.status}`}>
                                    <span className="agent-status-icon">{phase.icon}</span>
                                    <span className="agent-status-label">{phase.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Execution Plan */}
                    <div className="dashboard-section">
                        <div className="dashboard-section-title">
                            {goalState?.planTitle || 'Execution Plan'}
                        </div>
                        {goalState?.steps && goalState.steps.length > 0 ? (
                            <div className="step-list">
                                {goalState.steps.map((step) => (
                                    <div key={step.id} className={`step-item ${step.status}`}>
                                        <div className="step-number">
                                            {step.status === 'passed' ? '✓' : step.status === 'failed' ? '✗' : step.id}
                                        </div>
                                        <div className="step-info">
                                            <div className="step-action">{step.action}</div>
                                            <div className="step-tool">{step.tool}</div>
                                        </div>
                                        <span className={`step-status-badge ${step.status}`}>
                                            {step.status}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-state">
                                <div className="empty-state-icon">📋</div>
                                <span>Submit a goal to see the execution plan</span>
                            </div>
                        )}
                    </div>

                    {/* Outcome */}
                    {goalState?.status === 'completed' && (
                        <div className="dashboard-section">
                            <div className="dashboard-section-title">Outcome</div>
                            <div className="outcome-card">
                                <div className="outcome-stats">
                                    <div className="outcome-stat">
                                        <div className="outcome-stat-value">{goalState.stepsCompleted}</div>
                                        <div className="outcome-stat-label">Steps Done</div>
                                    </div>
                                    <div className="outcome-stat">
                                        <div className="outcome-stat-value">{goalState.steps.length}</div>
                                        <div className="outcome-stat-label">Total Steps</div>
                                    </div>
                                    <div className="outcome-stat">
                                        <div className="outcome-stat-value">{goalState.adaptations}</div>
                                        <div className="outcome-stat-label">Adaptations</div>
                                    </div>
                                </div>
                                {goalState.finalReport && (
                                    <div className="outcome-report">
                                        {goalState.finalReport}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </>
    );
}
