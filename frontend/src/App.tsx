import React, { useState, useEffect, useRef } from 'react';
import './index.css';
import { 
  Send, Shield, CheckCircle, AlertTriangle, 
  User, Briefcase, Mail, Link as LinkIcon, 
  Loader2, Sparkles, LogOut, ArrowRight
} from 'lucide-react';

interface Message {
  sender: 'user' | 'agent' | 'system';
  text: string;
}

export default function App() {
  // Visitor Info State
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Recruiter');
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
  
  // API URL binding (routed via localhost locally, pointing to public tunnel in production)
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // Attempt restoring session from local storage
    const savedSession = localStorage.getItem('visitor_session_id');
    const savedTier = localStorage.getItem('visitor_access_tier');
    const savedName = localStorage.getItem('visitor_name');
    if (savedSession && savedTier) {
      setSessionId(savedSession);
      setAccessTier(savedTier as 'FULL' | 'RESTRICTED');
      setVerified(true);
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
        body: JSON.stringify({ name, company, email, role, linkedin })
      });
      if (res.ok) {
        setOtpSent(true);
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to dispatch verification code.');
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
        body: JSON.stringify({ email, otp_code: otpCode, ip_address: '127.0.0.1' })
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setAccessTier(data.access_tier);
        setVerified(true);
        localStorage.setItem('visitor_session_id', data.session_id);
        localStorage.setItem('visitor_access_tier', data.access_tier);
        localStorage.setItem('visitor_name', name);
        
        setMessages([
          {
            sender: 'agent',
            text: `Hello ${name}! Access tier: ${data.access_tier}. Ask me anything about Andrew's projects.`
          }
        ]);
      } else {
        const data = await res.json();
        alert(data.detail || 'Verification code does not match.');
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
          'X-Session-ID': sessionId
        },
        body: JSON.stringify({ message: userText })
      });

      if (response.status === 403) {
        const data = await response.json();
        setBlocked(true);
        const match = data.message.match(/ip=(\d+\.\d+\.\d+\.\d+)/);
        if (match) setBlockedIp(match[1]);
        setMessages(prev => [...prev, { sender: 'system', text: data.message }]);
        setLoading(false);
        return;
      }

      if (!response.ok) {
        const data = await response.json();
        setMessages(prev => [...prev, { sender: 'system', text: data.detail || 'An error occurred.' }]);
        setLoading(false);
        return;
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        if (data.status === 'warning') {
          setSystemAlert(data.message);
          setMessages(prev => [...prev, { sender: 'agent', text: data.message }]);
        } else if (data.status === 'blocked') {
          setBlocked(true);
          setMessages(prev => [...prev, { sender: 'system', text: data.message }]);
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
    setVerified(false);
    setOtpSent(false);
    setMessages([]);
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
                  <option value="Recruiter">Recruiter</option>
                  <option value="Hiring Manager">Hiring Manager</option>
                  <option value="Technical Interviewer">Technical Interviewer</option>
                  <option value="General Visitor">General Visitor</option>
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

  // 3. Main Chat Interface
  return (
    <div className="w-[850px] h-[650px] glass-panel flex flex-col overflow-hidden animate-fade-in">
      {/* Header bar */}
      <div className="p-4 border-b border-white/5 flex justify-between items-center bg-slate-950/40">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <div>
            <h2 className="text-sm font-bold">Andrew Yeo Digital Twin</h2>
            <p className="text-xs text-slate-400 flex items-center gap-1">
              Access: <span className={accessTier === 'FULL' ? 'text-blue-400 font-semibold' : 'text-amber-500'}>{accessTier} Access</span>
            </p>
          </div>
        </div>
        <button onClick={handleLogout} className="text-slate-400 hover:text-white p-2 hover:bg-white/5 rounded-lg transition-colors">
          <LogOut className="w-4 h-4" />
        </button>
      </div>

      {/* Warnings alerts */}
      {systemAlert && (
        <div className="px-4 py-3 bg-amber-950/30 border-b border-amber-900/30 flex items-center gap-2 text-xs text-amber-300">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{systemAlert}</span>
        </div>
      )}

      {/* Chat logs messages panels */}
      <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-slate-900/20">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl p-4 text-sm leading-relaxed ${
              msg.sender === 'user' 
                ? 'bg-blue-600 text-white rounded-br-none' 
                : msg.sender === 'system'
                ? 'bg-red-950/40 border border-red-900/30 text-red-300 text-xs text-center mx-auto'
                : 'bg-slate-800/80 border border-white/5 text-slate-100 rounded-bl-none font-mono whitespace-pre-wrap'
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-800/80 border border-white/5 rounded-xl rounded-bl-none p-4 flex items-center gap-2 text-xs text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              Agent is reasoning...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input panel bar */}
      <form onSubmit={handleSendMessage} className="p-4 border-t border-white/5 bg-slate-950/30 flex gap-3">
        <input 
          type="text" 
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
  );
}
