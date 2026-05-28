"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { getAdminConfig } from '../actions/admin';
import { Upload, Play, Square, Activity, Server } from 'lucide-react';

export default function AdminDashboard() {
    const router = useRouter();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const [isAdmin, setIsAdmin] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [workerState, setWorkerState] = useState("Unknown");
    const [maintenanceState, setMaintenanceState] = useState("Unknown");
    const [file, setFile] = useState<File | null>(null);
    const [uploadStatus, setUploadStatus] = useState("");
    
    // Config states
    const [maxCapacity, setMaxCapacity] = useState("1000");
    const [isSavingConfig, setIsSavingConfig] = useState(false);
    const [configStatus, setConfigStatus] = useState("");
    const [isTriggering, setIsTriggering] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);

    const loadingPhrases = [
        "Parsing JSON structure...",
        "Validating metadata fields...",
        "Pinging Iota Cluster...",
        "Generating dense embeddings...",
        "Vectorizing document chunks...",
        "Ingesting into longterm_db...",
        "Optimizing Qdrant indices..."
    ];
    const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0);

    useEffect(() => {
        if (uploadStatus !== "Uploading...") {
            setLoadingPhraseIndex(0);
            return;
        }
        const interval = setInterval(() => {
            setLoadingPhraseIndex(prev => (prev + 1) % loadingPhrases.length);
        }, 1500);
        return () => clearInterval(interval);
    }, [uploadStatus]);

    useEffect(() => {
        const verifyAdmin = async () => {
            if (document.cookie.includes('is_admin=true')) {
                setIsAdmin(true);
                fetchWorkerStatus();
                fetchWorkerConfig();
                fetchLogs();
                setIsLoading(false);
                return;
            }
            router.push('/login');
        };
        verifyAdmin();
        
        // Poll logs every 5 seconds if admin
        const interval = setInterval(() => {
            if (document.cookie.includes('is_admin=true')) {
                fetchLogs();
            }
        }, 5000);
        return () => clearInterval(interval);
    }, [router]);

    const fetchWorkerStatus = async () => {
        try {
            const res = await fetch(`${apiUrl}/api/admin/worker/status`);
            const data = await res.json();
            setWorkerState(data.worker_state);
            
            const mRes = await fetch(`${apiUrl}/api/admin/worker/maintenance/status`);
            const mData = await mRes.json();
            setMaintenanceState(mData.worker_state);
        } catch(e) {
            console.error(e);
        }
    };

    const fetchWorkerConfig = async () => {
        try {
            const res = await fetch(`${apiUrl}/api/admin/worker/config`);
            const data = await res.json();
            setMaxCapacity(data.max_capacity.toString());
        } catch(e) {
            console.error(e);
        }
    };

    const fetchLogs = async () => {
        try {
            const res = await fetch(`${apiUrl}/api/admin/worker/logs`);
            const data = await res.json();
            if (data.logs) {
                setLogs(data.logs);
            }
        } catch(e) {
            console.error(e);
        }
    };

    const saveConfig = async () => {
        setIsSavingConfig(true);
        setConfigStatus("");
        try {
            const res = await fetch(`${apiUrl}/api/admin/worker/config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    max_capacity: parseInt(maxCapacity) || 1000
                })
            });
            if (res.ok) setConfigStatus("Settings saved successfully!");
            else setConfigStatus("Failed to save settings.");
        } catch(e) {
            setConfigStatus("Error saving settings.");
        }
        setIsSavingConfig(false);
        setTimeout(() => setConfigStatus(""), 3000);
    };

    const toggleWorker = async (start: boolean) => {
        const endpoint = start ? "start" : "stop";
        try {
            await fetch(`${apiUrl}/api/admin/worker/${endpoint}`, { method: "POST" });
            fetchWorkerStatus();
        } catch(e) {
            console.error(e);
        }
    };

    const toggleMaintenanceWorker = async (start: boolean) => {
        const endpoint = start ? "start" : "stop";
        try {
            await fetch(`${apiUrl}/api/admin/worker/maintenance/${endpoint}`, { method: "POST" });
            fetchWorkerStatus();
        } catch(e) {
            console.error(e);
        }
    };

    const triggerExtraction = async () => {
        setIsTriggering(true);
        try {
            await fetch(`${apiUrl}/api/admin/trigger-email-worker`, { method: "POST" });
            fetchLogs();
        } catch(e) {
            console.error(e);
        }
        setTimeout(() => setIsTriggering(false), 2000);
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploadStatus("Uploading...");
        
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            const res = await fetch(`${apiUrl}/api/admin/upload-json`, {
                method: "POST",
                body: formData,
            });
            const data = await res.json();
            if (res.ok) {
                setUploadStatus(`Success: ${data.message}`);
                setFile(null);
            } else {
                setUploadStatus(`Error: ${data.detail || 'Upload failed'}`);
            }
        } catch(e) {
            setUploadStatus("Error uploading file.");
        }
    };

    if (isLoading) return <div className="min-h-screen bg-[#0D131F] flex items-center justify-center"><div className="w-8 h-8 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div></div>;

    if (!isAdmin) return null;

    return (
        <div className="min-h-screen w-full bg-[#0D131F] text-white p-4 lg:p-8 font-sans">
            <div className="max-w-[1600px] w-full mx-auto space-y-8">
                <header className="border-b border-[#22304A] pb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-2xl md:text-3xl font-extrabold flex items-center gap-3">
                            <Server className="text-emerald-500 shrink-0" size={32} />
                            <span>Admin <span className="text-[#FBBF24]">Command Center</span></span>
                        </h1>
                        <p className="text-sm md:text-base text-gray-400 mt-2">Manage the RAGnarok core intelligence and agent workers.</p>
                    </div>
                    <button onClick={() => router.push('/')} className="px-4 py-2 w-full sm:w-auto rounded-lg bg-[#141C2B] hover:bg-[#1A2639] border border-[#22304A] transition font-semibold text-sm">
                        Back to Chat
                    </button>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column: Controls */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Worker Control */}
                        <div className="bg-[#141C2B] border border-[#22304A] rounded-2xl p-6 shadow-xl relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-bl-full blur-2xl"></div>
                        <h2 className="text-xl font-bold flex items-center gap-2 mb-6">
                            <Activity className={workerState === "Active" ? "text-emerald-500" : "text-red-500"} />
                            Google Workspace Webhook
                        </h2>
                        
                        <div className="flex items-center gap-4 mb-8">
                            <span className="text-gray-400 font-medium">Webhook Status:</span>
                            <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border ${workerState === "Active" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                                {workerState === "Active" ? "Accepting Pushes" : "Access Denied"}
                            </span>
                        </div>
                        
                        <div className="grid grid-cols-1 gap-4 mb-6">
                            <div>
                                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Max Capacity (Emails)</label>
                                <input 
                                    type="number" 
                                    value={maxCapacity} 
                                    onChange={(e) => setMaxCapacity(e.target.value)} 
                                    className="w-full bg-[#0D131F] border border-[#22304A] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500 transition"
                                />
                            </div>
                        </div>
                        
                        <div className="flex gap-3 mb-6">
                            <button 
                                onClick={saveConfig}
                                disabled={isSavingConfig}
                                className="w-full py-2 rounded-lg bg-[#22304A] hover:bg-[#2A374A] border border-[#304163] transition text-sm font-semibold flex items-center justify-center"
                            >
                                {isSavingConfig ? "Saving..." : "Save Settings"}
                            </button>
                        </div>
                        {configStatus && <p className={`text-xs mb-4 text-center ${configStatus.includes("Error") || configStatus.includes("Failed") ? "text-red-400" : "text-emerald-400"}`}>{configStatus}</p>}

                        <div className="mb-6">
                            <button 
                                onClick={triggerExtraction}
                                disabled={isTriggering || workerState !== "Active"}
                                className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm font-bold text-white shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2"
                            >
                                <Activity size={18} />
                                {isTriggering ? "Commanding Google Servers..." : "Command Google to Push Now"}
                            </button>
                        </div>

                        <div className="flex flex-col sm:flex-row gap-4">
                            <button 
                                onClick={() => toggleWorker(true)}
                                disabled={workerState === "Active"}
                                className="flex-1 py-3 px-4 rounded-xl flex items-center justify-center gap-2 font-bold transition disabled:opacity-50 disabled:cursor-not-allowed bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                            >
                                <Play size={18} /> Allow Webhook
                            </button>
                            <button 
                                onClick={() => toggleWorker(false)}
                                disabled={workerState === "Inactive"}
                                className="flex-1 py-3 px-4 rounded-xl flex items-center justify-center gap-2 font-bold transition disabled:opacity-50 disabled:cursor-not-allowed bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20"
                            >
                                <Square size={18} /> Block Webhook
                            </button>
                        </div>
                        </div>

                        {/* Maintenance Worker Control */}
                        <div className="bg-[#141C2B] border border-[#22304A] rounded-2xl p-6 shadow-xl relative overflow-hidden">
                            <h2 className="text-xl font-bold flex items-center gap-2 mb-6">
                                <Server className={maintenanceState === "Active" ? "text-emerald-500" : "text-red-500"} />
                                Maintenance Worker (Deduplication)
                            </h2>
                            
                            <div className="flex items-center gap-4 mb-8">
                                <span className="text-gray-400 font-medium">Status:</span>
                                <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border ${maintenanceState === "Active" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                                    {maintenanceState === "Active" ? "Running" : "Stopped"}
                                </span>
                            </div>
                            
                            <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                                This worker runs every 5 minutes in the background to find and remove duplicate entries in the Short-Term Database, keeping only the most recent copies.
                            </p>
                            
                            <div className="flex flex-col sm:flex-row gap-4">
                                <button 
                                    onClick={() => toggleMaintenanceWorker(true)}
                                    disabled={maintenanceState === "Active"}
                                    className="flex-1 py-3 px-4 rounded-xl flex items-center justify-center gap-2 font-bold transition disabled:opacity-50 disabled:cursor-not-allowed bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                                >
                                    <Play size={18} /> Start Maintenance
                                </button>
                                <button 
                                    onClick={() => toggleMaintenanceWorker(false)}
                                    disabled={maintenanceState === "Inactive"}
                                    className="flex-1 py-3 px-4 rounded-xl flex items-center justify-center gap-2 font-bold transition disabled:opacity-50 disabled:cursor-not-allowed bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20"
                                >
                                    <Square size={18} /> Stop Maintenance
                                </button>
                            </div>
                        </div>

                    {/* JSON Upload */}
                    <div className="bg-[#141C2B] border border-[#22304A] rounded-2xl p-6 shadow-xl relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-[#FBBF24]/10 rounded-bl-full blur-2xl"></div>
                        <h2 className="text-xl font-bold flex items-center gap-2 mb-6">
                            <Upload className="text-[#FBBF24]" />
                            Ingest Knowledge Base
                        </h2>
                        
                        <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                            Upload a JSON file containing structural campus rules, schemes, or guidelines. This will be automatically embedded and added to the <code className="bg-[#0D131F] px-1.5 py-0.5 rounded text-xs text-indigo-400 border border-[#22304A]">longterm_db</code> collection.
                        </p>

                        <div className="space-y-4 relative z-10">
                            <input 
                                type="file" 
                                accept=".json"
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                                className="block w-full text-sm text-gray-400 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-[#1A2639] file:text-white hover:file:bg-[#22304A] transition cursor-pointer"
                            />
                            
                            <button 
                                onClick={handleUpload}
                                disabled={!file || uploadStatus === "Uploading..."}
                                className={`w-full py-3 px-4 rounded-xl flex items-center justify-center gap-3 font-bold transition disabled:cursor-not-allowed shadow-lg ${uploadStatus === "Uploading..." ? "bg-indigo-600/80 text-white" : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-600/20 disabled:opacity-50"}`}
                            >
                                {uploadStatus === "Uploading..." ? (
                                    <>
                                        <div className="w-5 h-5 rounded-full border-2 border-white border-t-transparent animate-spin shrink-0"></div>
                                        <span className="animate-pulse truncate">{loadingPhrases[loadingPhraseIndex]}</span>
                                    </>
                                ) : (
                                    <><Upload size={18} /> Upload & Ingest</>
                                )}
                            </button>
                            
                            {uploadStatus && uploadStatus !== "Uploading..." && (
                                <div className={`p-3 rounded-lg text-sm font-medium ${uploadStatus.startsWith('Error') ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                                    {uploadStatus}
                                </div>
                            )}
                        </div>
                    </div>
                    </div>
                    
                    {/* Right Column: Live Logs */}
                    <div className="lg:col-span-1 bg-[#141C2B] border border-[#22304A] rounded-2xl p-6 shadow-xl flex flex-col h-[calc(100vh-12rem)] min-h-[400px]">
                        <h2 className="text-xl font-bold flex items-center gap-2 mb-4 border-b border-[#22304A] pb-4">
                            <Server className="text-indigo-400" size={20} />
                            Live Terminal Logs
                        </h2>
                        
                        <div className="flex-1 bg-[#0D131F] rounded-xl border border-[#22304A] p-4 font-mono text-xs overflow-y-auto space-y-2">
                            {logs.length === 0 ? (
                                <p className="text-gray-500 italic">No logs available. Start the worker to see output.</p>
                            ) : (
                                logs.map((log, index) => (
                                    <div key={index} className="text-gray-300 break-words">
                                        {log.includes('Error') || log.includes('Failed') ? (
                                            <span className="text-red-400">{log}</span>
                                        ) : log.includes('Capacity exceeded') || log.includes('Deleted') ? (
                                            <span className="text-yellow-400">{log}</span>
                                        ) : log.includes('Successfully') ? (
                                            <span className="text-emerald-400">{log}</span>
                                        ) : (
                                            log
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
