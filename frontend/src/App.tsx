import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Shield, CheckCircle, AlertTriangle, 
  User, Briefcase, Mail, Link as LinkIcon, 
  Loader2, Sparkles, LogOut, ArrowRight
} from 'lucide-react';
import { MermaidBlock } from './components/MermaidBlock';

interface Message {
  sender: 'user' | 'agent' | 'system';
  text: string;
}

function parseInlineStyles(rawText: unknown): React.ReactNode[] {
  const text = typeof rawText === 'string' ? rawText : '';
  if (!text) return [];
  const boldParts = text.split(/(\*\*.*?\*\*)/g);
  return boldParts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="markdown-strong">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function parseMarkdown(rawText: unknown): React.ReactNode {
  const text = typeof rawText === 'string' ? rawText : (rawText ? JSON.stringify(rawText) : '');
  if (!text) return null;
  const parts = text.split(/(```[\s\S]*?(?:```|$))/g);

  return (
    <div className="markdown-content">
      {parts.map((part, index) => {
        if (part.startsWith('```')) {
          const isClosed = part.endsWith('```');
          const codeContent = isClosed ? part.slice(3, -3) : part.slice(3);
          const match = codeContent.match(/^(\w*)\n([\s\S]*)$/);
          const lang = match ? match[1] : '';
          const code = match ? match[2].trim() : codeContent.trim();

          if (lang === 'mermaid') {
            if (!isClosed) {
              return (
                <div key={index} className="code-block-container animate-pulse">
                  <div className="code-block-lang">mermaid (generating diagram...)</div>
                  <pre className="code-block-pre">
                    <code className="code-block-code">{code}</code>
                  </pre>
                </div>
              );
            }
            return <MermaidBlock key={index} chart={code} />;
          }

          return (
            <div key={index} className="code-block-container">
              {lang && <div className="code-block-lang">{lang}</div>}
              <pre className="code-block-pre">
                <code className="code-block-code">{code}</code>
              </pre>
            </div>
          );
        }

        const lines = part.split('\n');
        return (
          <div key={index}>
            {lines.map((line, lineIndex) => {
              if (line.startsWith('### ')) {
                return <h3 key={lineIndex} className="markdown-h3">{parseInlineStyles(line.slice(4))}</h3>;
              }
              if (line.startsWith('## ')) {
                return <h2 key={lineIndex} className="markdown-h2">{parseInlineStyles(line.slice(3))}</h2>;
              }
              if (line.startsWith('- ')) {
                return (
                  <ul key={lineIndex} className="markdown-ul">
                    <li className="markdown-li">{parseInlineStyles(line.slice(2))}</li>
                  </ul>
                );
              }
              if (line.trim() === '') {
                return <div key={lineIndex} className="markdown-br" />;
              }
              return (
                <p key={lineIndex} className="markdown-p">
                  {parseInlineStyles(line)}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}


export default function App() {
  // Visitor Info State
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('HR Recruiter');
  const [linkedin, setLinkedin] = useState('');
  const [otpCode, setOtpCode] = useState('');
  
  // App Verification States
  const [otpSent, setOtpSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [accessTier, setAccessTier] = useState<'FULL' | 'RESTRICTED'>('RESTRICTED');
  
  // Chat States
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [systemAlert, setSystemAlert] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [blockedIp, setBlockedIp] = useState('127.0.0.1');

  // Appeal States
  const [appealName, setAppealName] = useState('');
  const [appealEmail, setAppealEmail] = useState('');
  const [appealContact, setAppealContact] = useState('');
  const [appealReason, setAppealReason] = useState('');
  const [appealSubmitted, setAppealSubmitted] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Suggestions state & context classifier
  const [suggestions, setSuggestions] = useState<string[]>([
    "Tell me about Andrew's background",
    "What are his key technical skills?",
    "What is his experience with GenAI?"
  ]);

  useEffect(() => {
    if (messages.length === 0) return;
    const userText = messages
      .filter(m => m.sender === 'user')
      .map(m => m.text.toLowerCase())
      .join(' ');

    if (userText.includes('code') || userText.includes('database') || userText.includes('vector') || userText.includes('rag') || userText.includes('ingest') || userText.includes('backend') || userText.includes('architecture')) {
      setSuggestions([
        "How does pgvector search work?",
        "What is Andrew's microservices design?",
        "Explain the codebase ingestion pipeline"
      ]);
    } else if (userText.includes('security') || userText.includes('audit') || userText.includes('kyv') || userText.includes('limit') || userText.includes('block') || userText.includes('strike') || userText.includes('shield') || userText.includes('compliance')) {
      setSuggestions([
        "What is the Know Your Visitor loop?",
        "How does the PII Shield work?",
        "Explain UGreen NAS security patterns"
      ]);
    } else if (userText.includes('role') || userText.includes('job') || userText.includes('work') || userText.includes('career') || userText.includes('experience') || userText.includes('lead') || userText.includes('philosoph')) {
      setSuggestions([
        "What architect roles has he held?",
        "Tell me about his team leadership",
        "What is his Agentic AI design philosophy?"
      ]);
    } else {
      setSuggestions([
        "Tell me about Andrew's background",
        "What are his key technical skills?",
        "What is his experience with GenAI?"
      ]);
    }
  }, [messages]);

  const handleSuggestionClick = (q: string) => {
    setCurrentMessage(q);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  
  // API URL binding (routed via localhost locally, pointing to public tunnel in production)
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // Attempt restoring session from local storage
    const savedSession = localStorage.getItem('visitor_session_id');
    const savedTier = localStorage.getItem('visitor_access_tier');
    const savedName = localStorage.getItem('visitor_name');
    const savedCompany = localStorage.getItem('visitor_company');
    const savedRole = localStorage.getItem('visitor_role');
    if (savedSession && savedTier) {
      setSessionId(savedSession);
      setAccessTier(savedTier as 'FULL' | 'RESTRICTED');
      setVerified(true);
      if (savedName) setName(savedName);
      if (savedCompany) setCompany(savedCompany);
      if (savedRole) setRole(savedRole);
      setMessages([
        {
          sender: 'agent',
          text: `Hello ${savedName || 'Visitor'}! I am Andrew's Digital Twin. Ask me anything about his technical repositories, resume, or engineering capabilities.`
        }
      ]);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleRequestOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !company || !email) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/request_otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, company, email, role, role_type: role, linkedin })
      });
      if (res.ok) {
        setOtpSent(true);
      } else {
        const data = await res.json().catch(() => null);
        const msg = typeof data?.detail === 'string'
          ? data.detail
          : Array.isArray(data?.detail)
            ? data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : (data?.message || 'Failed to dispatch verification code.');
        alert(msg);
      }
    } catch (err) {
      alert('Failed to connect to verification server. Ensure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/verify_otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email, 
          otp_code: otpCode, 
          ip_address: '127.0.0.1',
          name,
          company,
          role,
          role_type: role
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setAccessTier(data.access_tier);
        setVerified(true);
        localStorage.setItem('visitor_session_id', data.session_id);
        localStorage.setItem('visitor_access_tier', data.access_tier);
        localStorage.setItem('visitor_name', name);
        localStorage.setItem('visitor_company', company);
        localStorage.setItem('visitor_role', role);
        
        setMessages([
          {
            sender: 'agent',
            text: `Hello ${name}! Access tier: ${data.access_tier}. Ask me anything about Andrew's projects.`
          }
        ]);
      } else {
        const data = await res.json().catch(() => null);
        const msg = typeof data?.detail === 'string'
          ? data.detail
          : Array.isArray(data?.detail)
            ? data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : (data?.message || 'Verification code does not match.');
        alert(msg);
      }
    } catch (err) {
      alert('Verification verification failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentMessage.trim() || loading) return;

    const activeSessionId = sessionId || localStorage.getItem('visitor_session_id') || '';
    if (!activeSessionId) {
      setMessages(prev => [...prev, { sender: 'system', text: 'Active session not found. Please log in again.' }]);
      return;
    }

    const userText = currentMessage;
    setMessages(prev => [...prev, { sender: 'user', text: userText }]);
    setCurrentMessage('');
    setLoading(true);
    setSystemAlert(null);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': activeSessionId
        },
        body: JSON.stringify({ 
          message: userText,
          session_id: activeSessionId
        })
      });

      if (response.status === 403) {
        const data = await response.json().catch(() => null);
        setBlocked(true);
        const errorMsg = (typeof data?.message === 'string' ? data.message : null) || 'Access Suspended: Policy violation detected.';
        const match = errorMsg.match(/ip=(\d+\.\d+\.\d+\.\d+)/);
        if (match) setBlockedIp(match[1]);
        setMessages(prev => [...prev, { sender: 'system', text: errorMsg }]);
        setLoading(false);
        return;
      }

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const errorText = typeof data?.detail === 'string'
          ? data.detail
          : Array.isArray(data?.detail)
            ? data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : (data?.message || 'An error occurred.');
        setMessages(prev => [...prev, { sender: 'system', text: errorText }]);
        setLoading(false);
        return;
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await response.json().catch(() => ({}));
        if (data.status === 'warning') {
          setSystemAlert(data.message);
          setMessages(prev => [...prev, { sender: 'agent', text: data.message }]);
        } else if (data.status === 'blocked') {
          setBlocked(true);
          setMessages(prev => [...prev, { sender: 'system', text: data.message }]);
        } else {
          // Standard JSON completion response
          const reply = data.response || data.message || data.content || '';
          if (reply) {
            setMessages(prev => [...prev, { sender: 'agent', text: reply }]);
          } else {
            setMessages(prev => [...prev, { sender: 'agent', text: 'No response received from agent.' }]);
          }
        }
        setLoading(false);
        return;
      }

      // Stream Reader for event-stream outputs
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let agentText = '';

      setMessages(prev => [...prev, { sender: 'agent', text: '' }]);

      while (reader) {
        const { value, done } = await reader.read();
        if (done) break;
        const textChunk = decoder.decode(value);
        const lines = textChunk.split('\n');
        
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const parsed = JSON.parse(line);
            
            // Check warning triggers inside stream
            if (parsed.status === 'warning') {
              setSystemAlert(parsed.message);
              agentText = parsed.message;
              setMessages(prev => {
                const next = [...prev];
                next.pop();
                next.push({ sender: 'agent', text: agentText });
                return next;
              });
              break;
            } else if (parsed.status === 'blocked') {
              setBlocked(true);
              break;
            }
            
            const content = parsed.message?.content || '';
            if (content) {
              agentText += content;
              setMessages(prev => {
                const next = [...prev];
                next.pop();
                next.push({ sender: 'agent', text: agentText });
                return next;
              });
            }
          } catch (e) {
            // Raw text fallback
            agentText += line;
            setMessages(prev => {
              const next = [...prev];
              next.pop();
              next.push({ sender: 'agent', text: agentText });
              return next;
            });
          }
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'system', text: 'Connection lost.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendAppeal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!appealName || !appealEmail || !appealContact || !appealReason) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/revalidate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip_address: blockedIp,
          real_name: appealName,
          real_email: appealEmail,
          contact_details: appealContact,
          reason: appealReason
        })
      });
      if (res.ok) {
        setAppealSubmitted(true);
      } else {
        alert('Failed to submit appeal. Try again.');
      }
    } catch (err) {
      alert('Appeal submission failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('visitor_session_id');
    localStorage.removeItem('visitor_access_tier');
    localStorage.removeItem('visitor_name');
    localStorage.removeItem('visitor_company');
    localStorage.removeItem('visitor_role');
    setVerified(false);
    setOtpSent(false);
    setMessages([]);
    setName('');
    setCompany('');
    setEmail('');
    setOtpCode('');
  };

  // 1. Blocked Overlay Screen View
  if (blocked) {
    return (
      <div className="w-[480px] p-8 glass-panel border-red-900/30 text-center animate-fade-in">
        <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold mb-2">Access Suspended</h2>
        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          Your session was locked out due to multiple system instructions override attempts. To appeal, verify your identity:
        </p>

        {!appealSubmitted ? (
          <form onSubmit={handleSendAppeal} className="space-y-4 text-left">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Full Name</label>
              <input 
                type="text" 
                required 
                value={appealName} 
                onChange={e => setAppealName(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Corporate Email</label>
              <input 
                type="email" 
                required 
                value={appealEmail} 
                onChange={e => setAppealEmail(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Contact Number</label>
              <input 
                type="text" 
                required 
                value={appealContact} 
                onChange={e => setAppealContact(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Reason for Security Violations</label>
              <textarea 
                required 
                rows={3} 
                value={appealReason} 
                onChange={e => setAppealReason(e.target.value)} 
                className="w-full glass-input resize-none" 
              />
            </div>
            <button type="submit" disabled={loading} className="w-full glass-button flex items-center justify-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit Revalidation Request'}
            </button>
          </form>
        ) : (
          <div className="p-6 bg-slate-900/50 rounded-lg border border-slate-800">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
            <h3 className="font-semibold mb-1">Appeal Submitted</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your revalidation request has been sent. Your access will be restored if details match corporate registers.
            </p>
          </div>
        )}
      </div>
    );
  }

  // 2. Gateway Welcome Sign-in card views
  if (!verified) {
    return (
      <div className="w-[420px] p-8 glass-panel animate-fade-in">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-blue-900/30 rounded-lg border border-blue-500/20">
            <Sparkles className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold">Andrew Yeo's Digital Twin</h1>
            <p className="text-xs text-slate-400">Technical Interview Gateway</p>
          </div>
        </div>

        {!otpSent ? (
          <form onSubmit={handleRequestOTP} className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1 flex items-center gap-1"><User className="w-3 h-3" /> Full Name</label>
              <input 
                type="text" 
                required 
                placeholder="Sarah Recruiter" 
                value={name} 
                onChange={e => setName(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1 flex items-center gap-1"><Briefcase className="w-3 h-3" /> Company</label>
              <input 
                type="text" 
                required 
                placeholder="Google" 
                value={company} 
                onChange={e => setCompany(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1 flex items-center gap-1"><Mail className="w-3 h-3" /> Professional Email</label>
              <input 
                type="email" 
                required 
                placeholder="sarah@google.com" 
                value={email} 
                onChange={e => setEmail(e.target.value)} 
                className="w-full glass-input" 
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Your Role</label>
                <select value={role} onChange={e => setRole(e.target.value)} className="w-full glass-input">
                  <option value="HR Recruiter">HR Recruiter (Max 15 Mins)</option>
                  <option value="Technical Interviewer">Technical Interviewer (Max 30 Mins)</option>
                  <option value="Founder/Builder Collaborator">Founder/Builder (Max 40 Mins)</option>
                  <option value="Media / Press">Media / Press (Max 20 Mins)</option>
                  <option value="Cultural Fit Interview">Cultural Fit (Max 20 Mins)</option>
                  <option value="Others / Guest">Others / Guest (Max 3 Qs)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1 flex items-center gap-1"><LinkIcon className="w-3 h-3" /> LinkedIn (Opt)</label>
                <input 
                  type="text" 
                  placeholder="linkedin.com/in/..." 
                  value={linkedin} 
                  onChange={e => setLinkedin(e.target.value)} 
                  className="w-full glass-input" 
                />
              </div>
            </div>
            <button type="submit" disabled={loading} className="w-full glass-button flex items-center justify-center gap-2 mt-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Request Verification Code <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOTP} className="space-y-4">
            <div className="p-4 bg-blue-950/20 rounded-lg border border-blue-900/30 text-center mb-2">
              <Mail className="w-8 h-8 text-blue-400 mx-auto mb-2" />
              <h3 className="text-sm font-semibold">Verification Code Sent</h3>
              <p className="text-xs text-slate-400 mt-1">We sent a 6-digit OTP code to: <strong>{email}</strong></p>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Enter 6-Digit OTP</label>
              <input 
                type="text" 
                required 
                maxLength={6} 
                placeholder="123456" 
                value={otpCode} 
                onChange={e => setOtpCode(e.target.value)} 
                className="w-full glass-input text-center text-lg tracking-widest font-mono" 
              />
            </div>
            <button type="submit" disabled={loading} className="w-full glass-button flex items-center justify-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify & Launch Chat'}
            </button>
            <button type="button" onClick={() => setOtpSent(false)} className="w-full text-xs text-slate-400 hover:text-white mt-1 text-center block">
              Back to form
            </button>
          </form>
        )}
      </div>
    );
  }

  // 3. Main Widescreen Dashboard Interface
  return (
    <div className="app-container glass-panel animate-fade-in">
      {/* Sidebar Panel */}
      <div className="sidebar">
        <div className="flex items-center gap-2 mb-6">
          <Sparkles className="w-5 h-5 text-blue-400" />
          <h2 className="text-sm font-bold text-white">Andrew Yeo Twin</h2>
        </div>

        <div className="flex-1 space-y-4">
          <div className="p-3 bg-slate-950/40 rounded-lg border border-white/5">
            <span className="text-xs text-slate-400 block mb-1">Visitor</span>
            <span className="text-sm font-semibold text-white block">{name || 'Guest User'}</span>
            <span className="text-xs text-slate-400 block">{company || 'Independent'}</span>
          </div>

          <div className="p-3 bg-slate-950/40 rounded-lg border border-white/5">
            <span className="text-xs text-slate-400 block mb-1">Access Tier</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`status-badge ${accessTier === 'FULL' ? 'full' : 'restricted'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${accessTier === 'FULL' ? 'bg-blue-500 animate-pulse' : 'bg-amber-500'}`} />
                {accessTier} Access
              </span>
            </div>
            <span className="text-[10px] text-slate-400 mt-2 block leading-relaxed">
              {accessTier === 'FULL' 
                ? 'Full RAG context search enabled across Andrew\'s active repositories.' 
                : 'General bio/resume information. Ingested codebases locked.'}
            </span>
          </div>

          {accessTier === 'FULL' && (
            <div className="p-3 bg-slate-950/30 rounded-lg border border-blue-500/10 text-xs">
              <span className="text-blue-400 font-semibold block mb-1">RAG Search Status</span>
              <span className="text-slate-400 block">Postgres index: Cosine HNSW</span>
              <span className="text-slate-400 block mt-1">Embeddings: 113 vectors loaded</span>
            </div>
          )}

          {/* Dynamic Suggested Topics */}
          <div className="p-3 bg-slate-950/40 rounded-lg border border-white/5">
            <span className="text-xs text-slate-400 font-semibold block mb-2">Suggested Topics</span>
            <div className="space-y-2">
              {suggestions.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSuggestionClick(q)}
                  disabled={loading}
                  className="w-full text-left text-xs text-blue-400 hover:text-blue-300 bg-slate-950/30 hover:bg-slate-950/60 p-2 rounded border border-blue-500/10 transition-colors block"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button onClick={handleLogout} className="glass-button w-full flex items-center justify-center gap-2 mt-auto">
          <LogOut className="w-4 h-4" /> Sign Out
        </button>
      </div>

      {/* Main Chat Interface */}
      <div className="chat-main">
        {/* Chat header */}
        <div className="p-4 border-b border-white/5 flex justify-between items-center bg-slate-950/20">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs font-semibold text-slate-400">Agent Online</span>
          </div>
          <span className="text-xs font-mono text-slate-400">Andrew-Digital-Twin-LORA</span>
        </div>

        {/* System Alert banner */}
        {systemAlert && (
          <div className="px-4 py-3 bg-amber-950/30 border-b border-amber-900/30 flex items-center gap-2 text-xs text-amber-300">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{systemAlert}</span>
          </div>
        )}

        {/* Chat Messages */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`message-row ${msg.sender === 'user' ? 'user' : 'agent'}`}>
              {msg.sender === 'system' ? (
                <div className="chat-bubble system">{typeof msg.text === 'string' ? msg.text : JSON.stringify(msg.text)}</div>
              ) : (
                <div className={`chat-bubble ${msg.sender === 'user' ? 'user' : 'agent'}`}>
                  {msg.sender === 'user' 
                    ? (typeof msg.text === 'string' ? msg.text : JSON.stringify(msg.text))
                    : parseMarkdown(msg.text)}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="message-row agent">
              <div className="chat-bubble agent flex items-center gap-2 text-xs text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                Reasoning...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-white/5 bg-slate-950/20 flex gap-3">
          <input 
            type="text" 
            ref={inputRef}
            value={currentMessage} 
            onChange={e => setCurrentMessage(e.target.value)} 
            placeholder={accessTier === 'RESTRICTED' ? 'Ask resume/general questions (max 3 turns)...' : 'Ask technical code queries...'}
            className="flex-1 glass-input"
          />
          <button type="submit" disabled={loading || !currentMessage.trim()} className="glass-button flex items-center justify-center p-3">
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

