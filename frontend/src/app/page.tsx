"use client";

import React, { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { 
  Send, Menu, Plus, MessageSquare, Settings, User, X, Sun, Moon,
  GraduationCap, Calendar, Coffee, FileText, Zap, Compass, ChevronRight, Server, LogOut, Copy, Check
} from "lucide-react";
import { createClient } from '@/lib/supabase/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const CodeBlock = ({ node, inline, className, children, ...props }: any) => {
  const match = /language-(\w+)/.exec(className || '');
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  if (!inline && match) {
    return (
      <div className="relative group my-4 rounded-lg overflow-hidden bg-[#1E1E1E] border border-gray-700/50 shadow-xl">
        <div className="flex items-center justify-between px-4 py-2 bg-[#2D2D2D] border-b border-gray-700/50">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{match[1]}</span>
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-colors focus:outline-none flex items-center gap-1"
            aria-label="Copy code"
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
            <span className="text-[10px]">{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <div className="overflow-x-auto text-[13px] leading-relaxed">
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={match[1]}
            PreTag="div"
            customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      </div>
    );
  }
  return (
    <code className={`px-1.5 py-0.5 rounded-md text-[13px] font-mono bg-black/10 dark:bg-white/10 text-pink-600 dark:text-pink-400 ${className}`} {...props}>
      {children}
    </code>
  );
};

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  agent?: string;
  reasoning_steps?: string[];
}

interface ChatSession {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [isEditingLogs, setIsEditingLogs] = useState(false);
  const [selectedLogIds, setSelectedLogIds] = useState<string[]>([]);
  
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [serverStatus, setServerStatus] = useState<'green' | 'yellow' | 'red' | 'offline'>('green');
  const [isAdmin, setIsAdmin] = useState(false);
  const [username, setUsername] = useState<string>("User");
  const [userId, setUserId] = useState<string | null>(null);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isAppInstalled, setIsAppInstalled] = useState(false);
  
  const [loadingStatus, setLoadingStatus] = useState("Thinking...");

  useEffect(() => {
    if (!isLoading) {
      setLoadingStatus("Thinking...");
    }
  }, [isLoading]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 300;
    setShouldAutoScroll(isNearBottom);
  };

  useEffect(() => {
    if (shouldAutoScroll) {
      scrollToBottom(isStreaming ? "auto" : "smooth");
    }
  }, [messages, shouldAutoScroll, isStreaming]);

  // Load sessions on mount or auth change
  useEffect(() => {
    const loadSessions = async () => {
      if (isAdmin) {
        const saved = localStorage.getItem('ragnarok_admin_sessions');
        if (saved) {
          try {
            setSessions(JSON.parse(saved));
          } catch (e) {}
        }
      } else if (userId) {
        const supabase = createClient();
        const { data, error } = await supabase
          .from('chat_sessions')
          .select('*')
          .eq('user_id', userId)
          .order('updated_at', { ascending: false });
        
        if (data && !error) {
          const loaded: ChatSession[] = data.map(d => ({
            id: d.id,
            title: d.title,
            updatedAt: new Date(d.updated_at).getTime(),
            messages: d.messages
          }));
          setSessions(loaded);
        }
      }
    };
    loadSessions();
  }, [isAdmin, userId]);

  // Admin LocalStorage Sync
  useEffect(() => {
    if (isAdmin) {
      if (sessions.length > 0) {
        localStorage.setItem('ragnarok_admin_sessions', JSON.stringify(sessions));
      } else {
        localStorage.removeItem('ragnarok_admin_sessions');
      }
    }
  }, [sessions, isAdmin]);

  // Sync active messages to current session
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      const existingSession = sessions.find(s => s.id === currentSessionId);
      const isChanged = !existingSession || JSON.stringify(existingSession.messages) !== JSON.stringify(messages);
      
      if (isChanged) {
        const newTitle = existingSession?.title || (messages[0].content.substring(0, 30) + (messages[0].content.length > 30 ? "..." : ""));
        const now = Date.now();
        
        setSessions(prev => {
          const existingIdx = prev.findIndex(s => s.id === currentSessionId);
          let newSessions = [...prev];
          if (existingIdx >= 0) {
            newSessions[existingIdx] = { ...newSessions[existingIdx], messages, updatedAt: now };
          } else {
            newSessions.unshift({
              id: currentSessionId,
              title: newTitle,
              updatedAt: now,
              messages
            });
          }
          newSessions.sort((a, b) => b.updatedAt - a.updatedAt);
          return newSessions;
        });

        if (userId && !isAdmin) {
          const supabase = createClient();
          supabase.from('chat_sessions').upsert({
            id: currentSessionId,
            user_id: userId,
            title: newTitle,
            messages,
            updated_at: new Date(now).toISOString()
          }).then(({ error }) => {
            if (error) console.error("Failed to upsert session:", error);
          });
        }
      }
    }
  }, [messages, currentSessionId, userId, isAdmin]);

  const startNewSession = () => {
    setMessages([]);
    setCurrentSessionId("");
  };

  const loadSession = (id: string) => {
    if (isEditingLogs) return;
    const session = sessions.find(s => s.id === id);
    if (session) {
      setCurrentSessionId(id);
      setMessages(session.messages);
    }
  };

  const toggleSelectLog = (id: string) => {
    setSelectedLogIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const deleteSelectedLogs = async () => {
    if (userId && !isAdmin && selectedLogIds.length > 0) {
      const supabase = createClient();
      await supabase.from('chat_sessions').delete().in('id', selectedLogIds);
    }
    const newSessions = sessions.filter(s => !selectedLogIds.includes(s.id));
    setSessions(newSessions);
    setSelectedLogIds([]);
    setIsEditingLogs(false);
    if (selectedLogIds.includes(currentSessionId)) {
      startNewSession();
    }
  };

  useEffect(() => {
    // Check initial status
    setIsOnline(typeof navigator !== 'undefined' && navigator.onLine);

    const checkAdmin = async () => {
      let adminActive = false;
      if (document.cookie.includes('is_admin=true')) {
          setIsAdmin(true);
          setUsername("Iota Cluster");
          adminActive = true;
      }
      
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (user && !adminActive) {
        setUsername(user.user_metadata?.username || "User");
        setUserId(user.id);
      }
    };
    checkAdmin();

    const checkServerHealth = async () => {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        setServerStatus('offline');
        return;
      }
      try {
        const start = performance.now();
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/health`, { 
          method: 'GET',
          cache: 'no-store'
        });
        const end = performance.now();
        
        if (res.ok) {
          const latency = end - start;
          if (latency < 300) setServerStatus('green');
          else if (latency < 800) setServerStatus('yellow');
          else setServerStatus('red');
        } else {
          setServerStatus('offline');
        }
      } catch (e) {
        setServerStatus('offline');
      }
    };

    checkServerHealth();
    const intervalId = setInterval(checkServerHealth, 15000);

    const handleOnline = () => checkServerHealth();
    const handleOffline = () => setServerStatus('offline');

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      (window as any).deferredPrompt = e;
      setDeferredPrompt(e);
    };

    if (typeof window !== 'undefined') {
      // Check if already installed
      if (window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone) {
        setIsAppInstalled(true);
      } else {
        // If not installed, see if we already caught the event
        if ((window as any).deferredPrompt) {
          setDeferredPrompt((window as any).deferredPrompt);
        }
      }

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);
      window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
        window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
        clearInterval(intervalId);
      };
    }
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setDeferredPrompt(null);
    }
  };

  const handleSend = async (e?: React.FormEvent, presetText?: string) => {
    e?.preventDefault();
    const textToSend = presetText || input;
    if (!textToSend.trim() || isLoading) return;

    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
       activeSessionId = crypto.randomUUID();
       setCurrentSessionId(activeSessionId);
    }

    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: textToSend };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setShouldAutoScroll(true);

    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const historyToSend = messages.map(m => ({ role: m.role, content: m.content }));

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(isAdmin ? { "Authorization": `Bearer admin_bypass` } : (token ? { "Authorization": `Bearer ${token}` } : {}))
        },
        body: JSON.stringify({ 
          message: textToSend,
          chat_history: historyToSend
        })
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }

      setIsLoading(false); // Remove spinner as streaming starts
      setIsStreaming(true);

      const assistantId = crypto.randomUUID();
      setMessages(prev => [...prev, {
        id: assistantId,
        role: "assistant",
        content: "",
        agent: "RAGnarok",
        reasoning_steps: []
      }]);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let streamedText = "";
      let buffer = "";

      while (reader && !done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() || "";
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.chunk) {
                  streamedText += data.chunk;
                  setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: streamedText } : m));
                  if (shouldAutoScroll) {
                    scrollToBottom("auto");
                  }
                }
                if (data.route_taken) {
                  const agentName = data.route_taken === "academic_agent" ? "Academic Advisor" : data.route_taken === "campus_agent" ? "Campus Guide" : "RAGnarok Core";
                  setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, agent: agentName } : m));
                }
                if (data.status) {
                  setMessages(prev => prev.map(m => {
                    if (m.id === assistantId) {
                      const steps = m.reasoning_steps || [];
                      if (!steps.includes(data.status)) {
                        return { ...m, reasoning_steps: [...steps, data.status] };
                      }
                    }
                    return m;
                  }));
                  if (shouldAutoScroll) scrollToBottom("auto");
                }
                if (data.error) {
                  console.error(data.error);
                  streamedText = "⚠️ **Error:** " + data.error;
                  setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: streamedText } : m));
                }
              } catch (e) {}
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      const errorMessage: Message = { 
        id: crypto.randomUUID(), 
        role: "assistant", 
        content: "⚠️ **Connection Error**\n\nI couldn't reach the Iota Cluster. Please check the following:\n• Your internet connection is active\n• The campus network or VPN is connected (if required)\n• The backend services are currently online\n\nIf the issue persists, please try again later.",
        agent: "System"
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
    }
  };

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const toggleMobileSidebar = () => setIsMobileSidebarOpen(!isMobileSidebarOpen);
  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  return (
    <div className={`flex h-screen w-full font-sans overflow-hidden transition-colors duration-300 ${isDarkMode ? "dark bg-[#0D131F] text-gray-200" : "bg-[#F3F4F6] text-gray-800"}`}>
      
      {/* Mobile Sidebar Overlay */}
      {isMobileSidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden transition-opacity"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Unique RAGnarok Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50 flex flex-col transition-all duration-300 ease-in-out shrink-0
        ${isDarkMode ? "bg-[#141C2B] border-r border-[#22304A]" : "bg-white border-r border-gray-200 shadow-xl md:shadow-none"}
        ${isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        w-72 md:w-[280px]
        ${!isSidebarOpen ? "md:-ml-[280px]" : ""}
      `}>
        {/* Brand Header */}
        <div className="h-20 flex items-center justify-between px-5">
          <div className="flex items-center gap-3">
             <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-md bg-gradient-to-br from-[#1A2639] to-[#0D131F] border border-[#22304A]">
                <Image src="/RAG_logo.png" alt="Logo" fill sizes="40px" className="object-cover scale-110" />
             </div>
             <div className="flex flex-col">
               <span className={`font-bold tracking-wide text-lg ${isDarkMode ? "text-white" : "text-gray-900"}`}>RAG<span className="text-[#FBBF24]">narok</span></span>
               <span className="text-[10px] tracking-widest uppercase text-gray-500 font-semibold">IIT Ropar</span>
             </div>
          </div>
          <button className={`md:hidden p-2 ${isDarkMode ? "text-gray-400" : "text-gray-500"}`} onClick={toggleMobileSidebar}>
            <X size={20} />
          </button>
        </div>

        {/* Start New Session */}
        <div className="px-4 py-3">
          <button onClick={startNewSession} className={`group relative w-full flex items-center justify-center gap-2 py-3 rounded-xl overflow-hidden transition-all duration-300 ${isDarkMode ? "bg-gradient-to-r from-[#1E2E4A] to-[#1A2639] hover:from-[#253859] hover:to-[#1E2E4A] text-white border border-[#304163]" : "bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 text-indigo-900 border border-indigo-200 shadow-sm"}`}>
             <Plus size={18} className="group-hover:rotate-90 transition-transform duration-300" />
             <span className="font-semibold text-sm">New Session</span>
          </button>
        </div>
        
        {/* Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-6 scrollbar-hide">
          
          {/* Active Server Status */}
          <div>
            <h3 className={`text-[11px] uppercase tracking-wider font-bold mb-3 ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>Active Server</h3>
            <div className={`flex items-center justify-between w-full p-2.5 rounded-lg border ${isDarkMode ? "bg-[#1B273C] border-[#22304A] text-gray-300" : "bg-gray-50 border-gray-200 text-gray-700"}`}>
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-md bg-black flex items-center justify-center shadow-inner overflow-hidden relative">
                  <Image src="/logo_iota.png" alt="Iota" fill sizes="24px" className="object-cover scale-[1.3]" />
                </div>
                <div className="flex flex-col text-left">
                   <span className="text-sm font-bold tracking-wide">Iota Cluster</span>
                   <span className="text-[9px] uppercase tracking-widest text-gray-500 font-semibold">{serverStatus === 'offline' ? "Disconnected" : "Connected"}</span>
                </div>
              </div>
              <div className="relative flex h-2.5 w-2.5">
                {serverStatus !== 'offline' && (
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${serverStatus === 'green' ? 'bg-emerald-400' : serverStatus === 'yellow' ? 'bg-yellow-400' : 'bg-red-400'}`}></span>
                )}
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${serverStatus === 'offline' ? 'bg-red-500' : serverStatus === 'green' ? 'bg-emerald-500' : serverStatus === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
              </div>
            </div>
          </div>

          {/* Memory Log Only */}
          <div>
            <h3 className={`text-[11px] uppercase tracking-wider font-bold mb-3 flex items-center justify-between ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
              <span>Memory Log</span>
              <Settings 
                size={12} 
                className={`cursor-pointer transition-colors ${isEditingLogs ? "text-emerald-500" : "hover:text-gray-300"}`} 
                onClick={() => {
                  setIsEditingLogs(!isEditingLogs);
                  setSelectedLogIds([]);
                }}
              />
            </h3>
            <div className="space-y-1 relative before:absolute before:inset-y-0 before:left-3 before:w-px before:bg-gradient-to-b before:from-[#304163] before:to-transparent">
               {sessions.length === 0 ? (
                  <div className="text-xs text-gray-500 pl-4 py-2 italic">No saved memories</div>
               ) : sessions.map(session => (
                 <div key={session.id} className="flex items-center group">
                   {isEditingLogs && (
                     <input 
                       type="checkbox" 
                       checked={selectedLogIds.includes(session.id)}
                       onChange={() => toggleSelectLog(session.id)}
                       className="mr-2 ml-1 z-20 w-3 h-3 rounded accent-emerald-500 cursor-pointer"
                     />
                   )}
                   <button 
                     onClick={() => loadSession(session.id)}
                     className={`flex-1 flex items-start gap-4 p-2 rounded-lg transition-all ${!isEditingLogs ? (isDarkMode ? "hover:bg-[#1B273C]" : "hover:bg-gray-100") : ""} ${currentSessionId === session.id ? (isDarkMode ? "bg-[#1B273C]" : "bg-gray-100") : ""}`}
                   >
                     {!isEditingLogs && (
                       <div className={`relative z-10 mt-1 w-2 h-2 rounded-full ring-4 ${isDarkMode ? "ring-[#141C2B]" : "ring-white"} transition-colors ${currentSessionId === session.id ? "bg-emerald-500" : "bg-[#304163] group-hover:bg-gray-400"}`}></div>
                     )}
                     <div className="flex flex-col text-left overflow-hidden">
                       <span className={`text-sm truncate w-full font-medium ${isDarkMode ? (currentSessionId === session.id ? "text-emerald-400" : "text-gray-400 group-hover:text-gray-200") : (currentSessionId === session.id ? "text-emerald-600" : "text-gray-600")}`}>
                         {session.title}
                       </span>
                       <span className="text-[10px] text-gray-500">
                         {new Date(session.updatedAt).toLocaleDateString()}
                       </span>
                     </div>
                   </button>
                 </div>
               ))}
            </div>
            {isEditingLogs && selectedLogIds.length > 0 && (
              <button 
                onClick={deleteSelectedLogs}
                className="mt-3 w-full py-1.5 text-xs font-bold text-red-500 bg-red-500/10 hover:bg-red-500/20 rounded-lg transition-colors"
              >
                Delete Selected ({selectedLogIds.length})
              </button>
            )}
          </div>

          {/* Admin Panel Link */}
          {isAdmin && (
            <div>
              <h3 className={`text-[11px] uppercase tracking-wider font-bold mb-3 ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>Administration</h3>
              <button onClick={() => window.location.href='/admin'} className={`flex items-center gap-3 w-full p-2.5 rounded-lg transition-all group ${isDarkMode ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}>
                 <Server size={16} />
                 <span className="text-sm font-bold tracking-wide">Command Center</span>
              </button>
            </div>
          )}
        </div>

        {/* Profile Footer */}
        <div className={`p-4 border-t flex flex-col gap-3 ${isDarkMode ? "border-[#22304A] bg-[#101724]" : "border-gray-200 bg-gray-50"}`}>
           {!isAppInstalled && deferredPrompt && (
             <button onClick={handleInstallClick} className={`w-full py-2 px-3 rounded-lg flex items-center justify-center gap-2 font-semibold text-sm transition-all ${isDarkMode ? "bg-[#FBBF24] text-[#0D131F] hover:bg-yellow-400" : "bg-indigo-600 text-white hover:bg-indigo-700"}`}>
               <Image src="/RAG_logo.png" alt="Icon" width={16} height={16} className="rounded-full bg-black" />
               Install App
             </button>
           )}
           <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 border-2 border-[#1A2639]">
                  <User size={16} className="text-white" />
                </div>
                <div className="flex flex-col items-start">
                  <span className={`text-sm font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{username}</span>
                  <span className={`text-[10px] uppercase font-semibold ${isDarkMode ? "text-emerald-400" : "text-emerald-600"}`}>{isAdmin ? "System Admin" : "Verified Student"}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={async () => {
                    const supabase = createClient();
                    await supabase.auth.signOut();
                    document.cookie = "is_admin=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
                    window.location.href = '/login';
                  }}
                  title="Logout"
                  className={`p-2 rounded-full transition-colors ${isDarkMode ? "bg-[#1B273C] text-red-400 hover:text-white hover:bg-red-500" : "bg-gray-200 text-red-600 hover:text-white hover:bg-red-600"}`}>
                  <LogOut size={16} />
                </button>
                <button onClick={toggleTheme} className={`p-2 rounded-full transition-colors ${isDarkMode ? "bg-[#1B273C] text-gray-400 hover:text-white" : "bg-gray-200 text-gray-600 hover:text-black"}`}>
                  {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
                </button>
              </div>
           </div>
        </div>
      </aside>

      {/* Main Experience Area */}
      <main className="flex-1 flex flex-col h-full min-w-0 relative">
        
        {/* Floating Top Nav */}
        <header className="absolute top-4 left-4 right-4 z-10 flex justify-between pointer-events-none">
           <div className="pointer-events-auto">
             <button 
               className={`p-2.5 rounded-xl shadow-sm backdrop-blur-md border transition-all ${isDarkMode ? "bg-[#141C2B]/80 border-[#22304A] text-gray-300 hover:bg-[#1B273C]" : "bg-white/80 border-gray-200 text-gray-600 hover:bg-gray-50"}`} 
               onClick={() => {
                 if (window.innerWidth < 768) {
                   toggleMobileSidebar();
                 } else {
                   toggleSidebar();
                 }
               }}
             >
               <Menu size={20} />
             </button>
           </div>
        </header>

        {/* Interactive Chat Canvas */}
        <div className="flex-1 overflow-y-auto scroll-smooth relative flex flex-col" onScroll={handleScroll}>
          
          {messages.length === 0 ? (
            // Unique Empty State / Dashboard
            <div className="flex-1 flex flex-col items-center justify-center px-4 md:px-10 pb-40 pt-10 md:pb-28">
              <div className="w-20 h-20 md:w-24 md:h-24 rounded-3xl overflow-hidden shadow-2xl mb-8 relative bg-gradient-to-br from-[#1A2639] to-black border border-[#22304A] p-2">
                 <div className="absolute inset-0 bg-[#FBBF24] opacity-20 blur-xl rounded-full"></div>
                 <Image src="/RAG_logo.png" alt="Bot Logo" fill sizes="96px" className="object-cover scale-110 drop-shadow-lg" />
              </div>
              <h2 className={`text-3xl md:text-5xl font-extrabold mb-3 text-center tracking-tight ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                Hello, {username}.
              </h2>
              <p className={`text-lg md:text-xl text-center max-w-2xl font-medium ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                I'm connected to the <span className={isDarkMode ? "text-[#FBBF24]" : "text-yellow-600"}>Iota Cluster</span> and academic databases. How can I assist your campus life today?
              </p>

              {/* Action Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12 w-full max-w-4xl">
                 {[
                   { icon: Calendar, title: "Academic Calendar", desc: "Check upcoming mid-sems and holidays", color: "text-blue-400", bg: isDarkMode ? "bg-blue-400/10" : "bg-blue-50" },
                   { icon: Coffee, title: "Mess Menu", desc: "What's for dinner across hostels today?", color: "text-orange-400", bg: isDarkMode ? "bg-orange-400/10" : "bg-orange-50" },
                   { icon: FileText, title: "New at Campus", desc: "Summarize the latest cluster announcements", color: "text-emerald-400", bg: isDarkMode ? "bg-emerald-400/10" : "bg-emerald-50" }
                 ].map((action, i) => (
                   <button 
                     key={i} 
                     onClick={() => handleSend(undefined, action.title)}
                     className={`flex flex-col items-start p-5 rounded-2xl border transition-all duration-300 group hover:-translate-y-1 ${isDarkMode ? "bg-[#141C2B]/80 border-[#22304A] hover:bg-[#1A2639] hover:shadow-xl hover:shadow-black/20" : "bg-white border-gray-200 hover:shadow-lg"}`}
                   >
                     <div className={`p-3 rounded-xl mb-4 ${action.bg}`}>
                        <action.icon size={22} className={action.color} />
                     </div>
                     <span className={`font-semibold mb-1 ${isDarkMode ? "text-gray-200 group-hover:text-white" : "text-gray-800"}`}>{action.title}</span>
                     <span className={`text-xs text-left ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>{action.desc}</span>
                   </button>
                 ))}
              </div>
            </div>
          ) : (
            // Chat Feed
            <div className="p-4 md:p-8 space-y-8 pb-64 md:pb-80 max-w-5xl w-full mx-auto pt-20">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex w-full gap-4 md:gap-6 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-md relative overflow-hidden ${msg.role === "user" ? "bg-gradient-to-br from-indigo-500 to-purple-600 border border-indigo-400/30" : "bg-[#141C2B] border border-[#22304A]"}`}>
                    {msg.role === "user" ? (
                      <span className="text-white text-sm font-bold">{username.substring(0, 2).toUpperCase()}</span>
                    ) : (
                      <Image src="/RAG_logo.png" alt="Bot Logo" fill sizes="40px" className="object-cover scale-110" />
                    )}
                  </div>
                  <div className={`flex flex-col flex-1 min-w-0 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-2 mb-1.5 px-1">
                      <span className={`text-xs font-bold uppercase tracking-wider ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                        {msg.role === "user" ? "You" : msg.agent || "RAGnarok"}
                      </span>
                      {msg.agent && (
                         <span className="flex h-2 w-2 rounded-full bg-[#FBBF24]"></span>
                      )}
                    </div>
                    <div className={`p-4 md:p-5 rounded-2xl shadow-sm w-fit max-w-[95%] md:max-w-[85%] overflow-x-auto ${
                      msg.role === "user" 
                        ? "bg-indigo-600 text-white rounded-tr-sm" 
                        : isDarkMode ? "bg-[#141C2B] border border-[#22304A] text-gray-200 rounded-tl-sm" : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm"
                    }`}>
                      {msg.reasoning_steps && msg.reasoning_steps.length > 0 && (
                        <div className={`mb-4 pb-3 border-b border-dashed ${isDarkMode ? 'border-gray-700' : 'border-gray-300'} space-y-1.5`}>
                          {msg.reasoning_steps.map((step, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-xs font-mono">
                              <span className={`mt-[1px] ${isDarkMode ? 'text-[#FBBF24]' : 'text-yellow-600'}`}>▸</span>
                              <span className={isDarkMode ? 'text-gray-400' : 'text-gray-500'}>
                                {idx === msg.reasoning_steps!.length - 1 && !msg.content ? (
                                  <>
                                    {step.replace(/\.+$/, '')}
                                    <span className="inline-block tracking-widest typing-dots w-[14px] text-left"></span>
                                  </>
                                ) : (
                                  step
                                )}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      <div className={`prose prose-sm md:prose-base max-w-none ${msg.role === "user" ? "prose-invert prose-p:text-white" : isDarkMode ? "prose-invert" : ""} prose-p:leading-relaxed prose-pre:p-0 prose-pre:m-0 prose-pre:bg-transparent`}>
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                          components={{
                            code: CodeBlock as any,
                            a: ({node, ...props}) => <a target="_blank" rel="noopener noreferrer" {...props} className="text-emerald-500 hover:text-emerald-400 underline underline-offset-2" />,
                            table: ({node, ...props}) => <div className="overflow-x-auto my-4"><table className="min-w-full divide-y divide-gray-700/50" {...props} /></div>,
                            th: ({node, ...props}) => <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider bg-black/5 dark:bg-white/5" {...props} />,
                            td: ({node, ...props}) => <td className="px-4 py-3 text-sm whitespace-nowrap border-b border-gray-700/50" {...props} />
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex gap-4 md:gap-6 max-w-4xl mx-auto">
                  <div className="w-10 h-10 rounded-xl bg-[#141C2B] border border-[#22304A] flex items-center justify-center shrink-0 relative overflow-hidden shadow-md">
                    <Image src="/RAG_logo.png" alt="Bot Logo" fill sizes="40px" className="object-cover scale-110" />
                  </div>
                  <div className="flex flex-col items-start">
                    <span className={`text-xs font-bold uppercase tracking-wider mb-1.5 px-1 transition-all duration-300 ${isDarkMode ? "text-[#FBBF24]" : "text-yellow-600"}`}>
                      {loadingStatus}
                    </span>
                    <div className={`p-5 rounded-2xl shadow-sm flex items-center gap-2 rounded-tl-sm ${isDarkMode ? "bg-[#141C2B] border border-[#22304A]" : "bg-white border border-gray-200"}`}>
                      <div className={`w-2 h-2 rounded-full animate-bounce ${isDarkMode ? "bg-indigo-400" : "bg-indigo-600"}`}></div>
                      <div className={`w-2 h-2 rounded-full animate-bounce ${isDarkMode ? "bg-purple-400" : "bg-purple-600"}`} style={{ animationDelay: '0.2s' }}></div>
                      <div className={`w-2 h-2 rounded-full animate-bounce ${isDarkMode ? "bg-[#FBBF24]" : "bg-yellow-500"}`} style={{ animationDelay: '0.4s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Floating Intelligent Input Area */}
        <div className={`absolute bottom-0 left-0 right-0 p-4 md:p-8 pt-20 pointer-events-none ${isDarkMode ? "bg-gradient-to-t from-[#0D131F] via-[#0D131F]/90 to-transparent" : "bg-gradient-to-t from-[#F3F4F6] via-[#F3F4F6]/90 to-transparent"}`}>
          <div className="max-w-3xl mx-auto pointer-events-auto">
            <form onSubmit={(e) => handleSend(e)} className={`relative flex items-end p-2 rounded-3xl shadow-2xl border-2 transition-all duration-300 ${isDarkMode ? "bg-[#141C2B]/90 backdrop-blur-lg border-[#22304A] focus-within:border-[#FBBF24]/50 focus-within:bg-[#162032]" : "bg-white/90 backdrop-blur-lg border-gray-200 focus-within:border-indigo-300"}`}>
              <button type="button" className={`p-3 m-1 rounded-2xl transition-colors ${isDarkMode ? "bg-[#1B273C] text-gray-400 hover:text-white hover:bg-[#2A374A]" : "bg-gray-100 text-gray-500 hover:text-gray-900"}`}>
                 <Zap size={20} className={isDarkMode ? "text-[#FBBF24]" : "text-yellow-600"} />
              </button>
              
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={messages.length === 0 ? "Ask the cluster a question..." : "Continue the conversation..."}
                className={`w-full max-h-48 min-h-[56px] bg-transparent py-4 px-2 focus:outline-none resize-none font-medium text-[15px] ${isDarkMode ? "text-white placeholder-gray-500" : "text-gray-900 placeholder-gray-400"}`}
                rows={1}
              />
              
              <button 
                type="submit" 
                disabled={!input.trim() || isLoading}
                className={`p-3 m-1 rounded-2xl transition-all duration-300 flex items-center justify-center min-w-[56px] disabled:opacity-50 disabled:cursor-not-allowed ${input.trim() ? (isDarkMode ? "bg-[#FBBF24] text-[#0D131F] hover:bg-yellow-400 hover:shadow-lg hover:shadow-yellow-500/20" : "bg-indigo-600 text-white hover:bg-indigo-700") : (isDarkMode ? "bg-[#1B273C] text-gray-500" : "bg-gray-200 text-gray-400")}`}
              >
                <Send size={20} className={input.trim() ? "translate-x-0.5" : ""} />
              </button>
            </form>
            
            <div className={`flex items-center justify-center gap-2 mt-4 text-[11px] font-semibold tracking-wider uppercase ${isDarkMode ? "text-gray-600" : "text-gray-400"}`}>
              <span>RAGnarok v2.0</span>
              <span className="w-1 h-1 rounded-full bg-gray-500"></span>
              <span>IIT Ropar</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
