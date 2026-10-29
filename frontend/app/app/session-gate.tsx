"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Dashboard from "./dashboard";

type User = { id: number; email: string };

export default function SessionGate() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [mode, setMode] = useState<"login" | "register" | "verify">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/auth/me", { cache: "no-store", signal: controller.signal })
      .then((response) => response.ok ? response.json() : null)
      .then((result: User | null) => { if (!controller.signal.aborted) setUser(result); })
      .catch(() => { if (!controller.signal.aborted) setError("无法连接服务，请检查后端是否已启动。"); })
      .finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, []);

  const expire = useCallback(() => setUser(null), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (mode === "register" && password !== confirm) {
      setError("两次输入的密码不一致。");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "verify" ? { email, code } : { email, password }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "操作失败，请重试。");
      if (mode === "register") {
        setEmail(result.email);
        setCode("");
        setMode("verify");
        setNotice("验证码已发送，请查收邮箱。未收到时可在 60 秒后重发。");
      } else {
        setPassword("");
        setConfirm("");
        setCode("");
        setUser(result as User);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法连接服务，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "发送失败，请重试。");
      setCode("");
      setNotice("新验证码已发送，请查收邮箱。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发送失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("退出失败，请重试。");
      setUser(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "退出失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  if (checking) return <main className="auth-screen"><div className="auth-card" role="status">正在检查登录状态…</div></main>;
  if (user) return <Dashboard email={user.email} onLogout={logout} onSessionExpired={expire} logoutBusy={busy} logoutError={error} />;

  return <main className="auth-screen">
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-brand"><div className="brand-mark" aria-hidden="true"><span /><span /><span /></div><span>股市风险观察</span></div>
      <p className="eyebrow">A 股短期风险信号</p>
      <h1 id="auth-title">{mode === "login" ? "欢迎回来" : mode === "register" ? "创建账户" : "验证邮箱"}</h1>
      <p className="auth-intro">{mode === "verify" ? `已向 ${email} 发送 8 位验证码，10 分钟内有效。` : "登录后查询风险信号，并保存你自己的观察记录。"}</p>
      {mode !== "verify" && <div className="auth-tabs" role="group" aria-label="账户操作">
        <button type="button" className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); setNotice(""); }}>登录</button>
        <button type="button" className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); setNotice(""); }}>注册</button>
      </div>}
      <form onSubmit={submit} className="auth-form">
        {mode === "verify" ? <>
          <label htmlFor="auth-code">邮箱验证码</label>
          <input id="auth-code" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{8}" maxLength={8} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required />
        </> : <>
        <label htmlFor="auth-email">邮箱</label>
        <input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="auth-password">密码</label>
        <input id="auth-password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required />
        {mode === "register" && <><p className="auth-hint">至少 12 个字符。</p><label htmlFor="auth-confirm">确认密码</label><input id="auth-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></>}
        </>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        {notice && <p className="auth-notice" role="status">{notice}</p>}
        <button className="auth-submit" type="submit" disabled={busy}>{busy ? "请稍候…" : mode === "login" ? "登录" : mode === "register" ? "发送验证码" : "验证并创建账户"}</button>
      </form>
      {mode === "verify" && <div className="auth-actions">
        <button type="button" onClick={resendCode} disabled={busy}>重新发送验证码</button>
        <button type="button" onClick={() => { setMode("register"); setCode(""); setError(""); setNotice(""); }} disabled={busy}>修改邮箱</button>
      </div>}
      <p className="auth-footnote">模型结果仅供风险观察，不构成投资建议。</p>
    </section>
  </main>;
}
