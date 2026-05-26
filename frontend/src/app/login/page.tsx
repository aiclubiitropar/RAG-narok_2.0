"use client";

import React, { useState } from 'react';
import Image from 'next/image';
import { createClient } from '@/lib/supabase/client';
import { Mail, Lock, Loader2, ArrowRight, User } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [username, setUsername] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSignUp, setIsSignUp] = useState(false);
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [isForgotPassword, setIsForgotPassword] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const router = useRouter();
  const supabase = createClient();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const { getAdminConfig } = await import('../actions/admin');
      const adminConfig = await getAdminConfig();

      const adminEmail = adminConfig.adminEmail?.trim().toLowerCase();
      const inputEmail = email.trim().toLowerCase();

      if (adminEmail && inputEmail === adminEmail && !isForgotPassword) {
        if (isSignUp) {
          setError("This email already exists.");
          setIsLoading(false);
          return;
        } else {
          if (password !== adminConfig.adminPassword) {
            setError("Invalid admin credentials.");
            setIsLoading(false);
            return;
          }
          // Admin password is correct! Bypass Supabase entirely and set a cookie.
          document.cookie = "is_admin=true; path=/; max-age=86400";
          window.location.href = '/';
          return;
        }
      }

      // Forgot Password Flow
      if (isForgotPassword) {
        if (!isOtpSent) {
          if (!email.endsWith('@iitrpr.ac.in')) {
            setError("Only @iitrpr.ac.in accounts are permitted.");
            setIsLoading(false);
            return;
          }
          if (password !== confirmPassword) {
            setError("Passwords do not match.");
            setIsLoading(false);
            return;
          }

          const res = await fetch(`${apiUrl}/api/auth/send-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });
          const data = await res.json();
          if (!res.ok) {
            setError(data.detail || "Failed to send reset OTP.");
            setIsLoading(false);
            return;
          }
          
          setIsOtpSent(true);
          setSuccess("A password reset OTP has been sent to your email.");
          setIsLoading(false);
          return;
        } else {
          // Verify Reset OTP and Update Password
          if (!otp.trim() || otp.length !== 6) {
            setError("Please enter a valid 6-digit OTP.");
            setIsLoading(false);
            return;
          }

          const res = await fetch(`${apiUrl}/api/auth/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp, new_password: password })
          });
          const resData = await res.json();
          if (!res.ok) {
            setError(resData.detail || "Invalid or expired OTP.");
            setIsLoading(false);
            return;
          }

          setSuccess("Password updated successfully! You can now sign in.");
          setIsForgotPassword(false);
          setIsOtpSent(false);
          setOtp('');
          setPassword('');
          setConfirmPassword('');
          setIsLoading(false);
          return;
        }
      }

      // Regular User Flow
      if (isSignUp) {
        if (!isOtpSent) {
          // Enforce @iitrpr.ac.in domain for students
          if (!email.endsWith('@iitrpr.ac.in')) {
            setError("Only @iitrpr.ac.in accounts are permitted to access RAGnarok.");
            setIsLoading(false);
            return;
          }

          if (password !== confirmPassword) {
            setError("Passwords do not match.");
            setIsLoading(false);
            return;
          }

          if (!username.trim()) {
            setError("Username is required.");
            setIsLoading(false);
            return;
          }

          const res = await fetch(`${apiUrl}/api/auth/send-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });
          const data = await res.json();
          if (!res.ok) {
            setError(data.detail || "Failed to send OTP.");
            setIsLoading(false);
            return;
          }
          
          setIsOtpSent(true);
          setSuccess("An OTP has been sent to your email. It expires in 5 minutes.");
          setIsLoading(false);
          return;
        } else {
          // Verify OTP and SignUp
          if (!otp.trim() || otp.length !== 6) {
            setError("Please enter a valid 6-digit OTP.");
            setIsLoading(false);
            return;
          }

          const res = await fetch(`${apiUrl}/api/auth/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp })
          });
          const resData = await res.json();
          if (!res.ok) {
            setError(resData.detail || "Invalid or expired OTP.");
            setIsLoading(false);
            return;
          }

          // OTP is correct! Now create the Supabase account.
          const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
              data: {
                username
              }
            }
          });
          if (error) {
            setError(error.message);
          } else {
            setSuccess("Account created successfully! You can now sign in.");
            setIsSignUp(false);
            setIsOtpSent(false);
            setOtp('');
            setPassword('');
            setConfirmPassword('');
          }
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          setError(error.message);
        } else if (data.session) {
          router.push('/');
          router.refresh();
        }
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const resetState = () => {
    setIsSignUp(false);
    setIsForgotPassword(false);
    setError(null);
    setSuccess(null);
    setIsOtpSent(false);
    setOtp('');
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <div className="min-h-screen w-full bg-[#0D131F] text-white flex flex-col md:flex-row overflow-hidden font-sans">

      {/* Left side: Branding / Presentation */}
      <div className="hidden md:flex md:w-1/2 bg-[#141C2B] border-r border-[#22304A] p-12 flex-col justify-between relative overflow-hidden">
        {/* Decorative background elements */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-[#FBBF24] rounded-full mix-blend-multiply filter blur-[128px] opacity-20"></div>
          <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-indigo-600 rounded-full mix-blend-multiply filter blur-[128px] opacity-20"></div>
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <div className="relative w-12 h-12 rounded-xl overflow-hidden shadow-lg bg-gradient-to-br from-[#1A2639] to-black border border-[#22304A]" style={{ position: 'relative' }}>
            <Image src="/RAG_logo.png" alt="RAGnarok Logo" fill sizes="48px" className="object-cover scale-110" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold tracking-wide text-xl text-white">RAG<span className="text-[#FBBF24]">narok</span></span>
            <span className="text-xs tracking-widest uppercase text-gray-500 font-semibold">v2.0 Architecture</span>
          </div>
        </div>

        <div className="relative z-10 mt-20">
          <h1 className="text-4xl md:text-5xl font-extrabold mb-6 leading-tight tracking-tight">
            Your smart <span className="text-[#FBBF24]">campus companion.</span>
          </h1>
          <p className="text-lg text-gray-400 max-w-md font-medium leading-relaxed">
            Connect to the Iota Cluster, access your academic info, and query campus related information instantly with our RAG powered Agentic-network.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-4 text-sm font-semibold text-gray-500 tracking-wider uppercase mt-20">
          <span>IIT Ropar</span>
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
          <span>Systems Online</span>
        </div>
      </div>

      {/* Right side: Auth Form */}
      <div className="w-full md:w-1/2 flex items-center justify-center p-6 md:p-12 relative">
        <div className="w-full max-w-md space-y-8">

          <div className="md:hidden flex items-center justify-center gap-3 mb-8">
            <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-lg bg-gradient-to-br from-[#1A2639] to-black border border-[#22304A]" style={{ position: 'relative' }}>
              <Image src="/RAG_logo.png" alt="RAGnarok Logo" fill sizes="40px" className="object-cover scale-110" />
            </div>
            <span className="font-bold tracking-wide text-2xl text-white">RAG<span className="text-[#FBBF24]">narok</span></span>
          </div>

          <div className="text-center md:text-left">
            <h2 className="text-3xl font-bold tracking-tight mb-2">
              {isForgotPassword ? "Reset Password" : (isSignUp ? "Create an account" : "Welcome back")}
            </h2>
            <p className="text-gray-400 font-medium">
              {isForgotPassword ? "Enter your email and a new password" : (isSignUp ? "Join RAGnarok using your IIT Ropar email" : "Log in to your RAGnarok account to continue")}
            </p>
          </div>

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/50 text-red-400 text-sm font-medium">
              {error}
            </div>
          )}

          {success && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/50 text-emerald-400 text-sm font-medium">
              {success}
            </div>
          )}

          <form onSubmit={handleAuth} className="space-y-5">
            {isOtpSent ? (
              <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-300 ml-1">Verification Code (OTP)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock size={18} className="text-[#FBBF24]" />
                  </div>
                  <input
                    type="text"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    className="w-full bg-[#141C2B] border border-[#22304A] text-white rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-[#FBBF24]/50 focus:border-transparent transition-all placeholder-gray-600 font-bold tracking-[0.5em] text-center"
                    placeholder="123456"
                    maxLength={6}
                    required={isOtpSent}
                  />
                </div>
              </div>
            ) : (
              <>
                {isSignUp && !isForgotPassword && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-gray-300 ml-1">Username</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <User size={18} className="text-gray-500" />
                      </div>
                      <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        className="w-full bg-[#141C2B] border border-[#22304A] text-white rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-[#FBBF24]/50 focus:border-transparent transition-all placeholder-gray-600 font-medium"
                        placeholder="Choose a username"
                        required={isSignUp}
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-300 ml-1">Institute Email</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <Mail size={18} className="text-gray-500" />
                    </div>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-[#141C2B] border border-[#22304A] text-white rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-[#FBBF24]/50 focus:border-transparent transition-all placeholder-gray-600 font-medium"
                      placeholder="name@iitrpr.ac.in"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between ml-1">
                    <label className="text-sm font-semibold text-gray-300">{isForgotPassword ? "New Password" : "Password"}</label>
                    {!isSignUp && !isForgotPassword && (
                      <button type="button" onClick={() => { resetState(); setIsForgotPassword(true); }} className="text-xs text-[#FBBF24] hover:text-yellow-300 font-medium transition-colors">Forgot password?</button>
                    )}
                  </div>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <Lock size={18} className="text-gray-500" />
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-[#141C2B] border border-[#22304A] text-white rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-[#FBBF24]/50 focus:border-transparent transition-all placeholder-gray-600 font-medium"
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>

                {(isSignUp || isForgotPassword) && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-gray-300 ml-1">Confirm {isForgotPassword ? "New " : ""}Password</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <Lock size={18} className="text-gray-500" />
                      </div>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full bg-[#141C2B] border border-[#22304A] text-white rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-[#FBBF24]/50 focus:border-transparent transition-all placeholder-gray-600 font-medium"
                        placeholder="••••••••"
                        required={isSignUp || isForgotPassword}
                      />
                    </div>
                  </div>
                )}
              </>
            )}

            <button
              type="submit"
              disabled={isLoading || (isOtpSent ? (!otp || otp.length !== 6) : (!email || !password))}
              className="w-full bg-[#FBBF24] hover:bg-yellow-400 text-gray-900 font-bold rounded-xl py-3.5 px-4 flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-6 group"
            >
              {isLoading ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <>
                  <span>{isOtpSent ? (isForgotPassword ? "Verify & Reset" : "Verify & Sign up") : (isForgotPassword ? "Send Reset Code" : (isSignUp ? "Create Account" : "Sign in securely"))}</span>
                  <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 font-medium mt-8">
            {isSignUp || isForgotPassword ? (
              <>
                <button type="button" onClick={resetState} className="text-[#FBBF24] hover:text-yellow-300 transition-colors">Back to Sign in</button>
              </>
            ) : (
              <>
                Don't have an account? <button type="button" onClick={() => { resetState(); setIsSignUp(true); }} className="text-[#FBBF24] hover:text-yellow-300 transition-colors">Sign up</button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
