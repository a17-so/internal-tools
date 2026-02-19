"use client";

import * as React from "react";
import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  fetchApps,
  submitScrape,
  type ScrapeResponse,
} from "@/lib/outreach-api";

// ── Constants ──────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: "macro", label: "Macro" },
  { value: "micro", label: "Micro" },
  { value: "submicro", label: "Submicro" },
  { value: "ambassador", label: "Ambassador" },
  { value: "themepage", label: "Theme Page" },
  { value: "rawlead", label: "Raw Lead" },
];

const PASSWORD = "a17outreach";
const AUTH_KEY = "outreach_auth";

// ── Styled Card ────────────────────────────────────────────────────────────

function StyledCard({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <Card
      className={cn("border-zinc-800 hover:border-zinc-600/60", className)}
      {...props}
    />
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function OutreachPage() {
  // Auth state
  const [authed, setAuthed] = useState(false);
  const [pw, setPw] = useState("");
  const [pwError, setPwError] = useState(false);

  // Form state
  const [appConfigs, setAppConfigs] = useState<Record<string, any>>({});
  const apps = Object.keys(appConfigs);
  const [app, setApp] = useState("regen");
  const [category, setCategory] = useState("micro");
  const [url, setUrl] = useState("");
  const [senderProfile, setSenderProfile] = useState("ethan");

  // Submission state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScrapeResponse | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  // ── Auth check ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(AUTH_KEY);
      if (saved === "true") setAuthed(true);
    }
  }, []);

  function handleLogin() {
    if (pw === PASSWORD) {
      setAuthed(true);
      setPwError(false);
      sessionStorage.setItem(AUTH_KEY, "true");
    } else {
      setPwError(true);
    }
  }

  // ── Load apps on mount ─────────────────────────────────────────────────
  useEffect(() => {
    if (!authed) return;
    fetchApps()
      .then((configs) => {
        setAppConfigs(configs);
        const keys = Object.keys(configs);
        if (keys.length > 0) {
          if (configs['regen']) setApp("regen");
          else setApp(keys[0]);
        }
      })
      .catch((err) => {
        console.error("Failed to load apps", err);
        // Fallback or error handling
      });
  }, [authed]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentAppConfig = appConfigs[app];
  const senderProfiles = (currentAppConfig?.sender_profiles as string[]) || [];

  // Reset/Default sender profile when app changes
  useEffect(() => {
    if (senderProfiles.length > 0) {
      if (!senderProfiles.includes(senderProfile)) {
        // Validation: pick first available profile
        setSenderProfile(senderProfiles[0]);
      }
    }
  }, [app, senderProfiles, senderProfile]);

  // ── Submit ─────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!url.trim() || !senderProfile.trim()) return;

      setLoading(true);
      setError(null);
      setResult(null);

      try {
        const data = await submitScrape({
          app,
          creator_url: url.trim(),
          category,
          sender_profile: senderProfile || undefined,
        });
        setResult(data);
      } catch (err: any) {
        setError(err.message ?? "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [app, url, category, senderProfile]
  );

  // ── Copy helper ────────────────────────────────────────────────────────
  function copyText(text: string, label: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  // ── Password gate ──────────────────────────────────────────────────────
  if (!authed) {
    return (
      <div className="flex flex-col items-center justify-center w-screen h-screen bg-zinc-950">
        <h1 className="text-4xl font-semibold text-zinc-100 mb-2 sm:text-5xl">
          Outreach Tool
        </h1>
        <p className="text-sm text-zinc-500 mb-12">
          Enter password to continue
        </p>

        <div className="w-full max-w-sm px-6">
          <StyledCard>
            <div className="pt-4 pb-6 px-6 md:pt-6 md:pb-8 md:px-8">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleLogin();
                }}
                className="space-y-4 text-zinc-300"
              >
                <div className="space-y-2">
                  <label htmlFor="password" className="text-sm text-zinc-400">
                    Password
                  </label>
                  <Input
                    type="password"
                    id="password"
                    value={pw}
                    onChange={(e) => {
                      setPw(e.target.value);
                      setPwError(false);
                    }}
                    placeholder="Enter password"
                    autoFocus
                    className={cn(
                      "h-11 bg-zinc-900/60 text-zinc-100 placeholder:text-zinc-500 border-zinc-700/60 rounded-xl",
                      pwError && "border-red-500/60"
                    )}
                  />
                  {pwError && (
                    <p className="text-xs text-red-400">Wrong password.</p>
                  )}
                </div>
                <div className="flex justify-end">
                  <Button
                    type="submit"
                    className="bg-white text-black hover:bg-white/90 rounded-full px-6"
                  >
                    Unlock
                  </Button>
                </div>
              </form>
            </div>
          </StyledCard>
        </div>

        <p className="mt-12 text-sm text-zinc-700">internal tool</p>
      </div>
    );
  }

  // ── Main form ──────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen w-screen bg-zinc-950">
      <div className="mx-auto flex w-full max-w-2xl flex-col px-6 py-16 md:py-24">
        {/* Header */}
        <section className="flex flex-col items-center gap-4 mb-10">
          <h2 className="text-2xl text-zinc-100 font-medium md:text-3xl">
            Outreach Tool
          </h2>
          <p className="text-sm text-zinc-500">
            Paste a creator URL, pick a category, and get your DM + email ready.
          </p>
        </section>

        {/* Form Card */}
        <StyledCard>
          <div className="pt-4 pb-6 px-6 md:pt-6 md:pb-8 md:px-8">
            <form onSubmit={handleSubmit} className="space-y-6 text-zinc-300">
              {/* App selector */}
              <div className="space-y-2">
                <label htmlFor="app" className="text-sm text-zinc-400">
                  App
                </label>
                <select
                  id="app"
                  value={app}
                  onChange={(e) => setApp(e.target.value)}
                  className="flex h-11 w-full rounded-xl border border-zinc-700/60 bg-zinc-900/60 px-3 py-1 text-sm text-zinc-100 outline-none transition focus-visible:border-zinc-400 focus-visible:ring-zinc-400/30 focus-visible:ring-[3px]"
                >
                  {apps.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </div>

              {/* Category */}
              <div className="space-y-2">
                <label className="text-sm text-zinc-400">Category</label>
                <div className="grid grid-cols-3 gap-2">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => setCategory(c.value)}
                      className={cn(
                        "rounded-xl border px-3 py-2.5 text-xs font-medium transition-all",
                        category === c.value
                          ? "border-white bg-white text-black"
                          : "border-zinc-700/60 bg-zinc-900/60 text-zinc-400 hover:border-zinc-500/60 hover:text-zinc-200"
                      )}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sender Profile */}
              <div className="space-y-2">
                <label htmlFor="senderProfile" className="text-sm text-zinc-400">
                  Sender Profile
                </label>
                {senderProfiles.length > 0 ? (
                  <div className="relative">
                    <select
                      id="senderProfile"
                      value={senderProfile}
                      onChange={(e) => setSenderProfile(e.target.value)}
                      className="flex h-11 w-full rounded-xl border border-zinc-700/60 bg-zinc-900/60 px-3 py-1 text-sm text-zinc-100 outline-none transition focus-visible:border-zinc-400 focus-visible:ring-zinc-400/30 focus-visible:ring-[3px]"
                    >
                      {senderProfiles.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <Input
                    type="text"
                    id="senderProfile"
                    value={senderProfile}
                    onChange={(e) => setSenderProfile(e.target.value)}
                    placeholder="e.g. ethan"
                    required
                    className="h-11 bg-zinc-900/60 text-zinc-100 placeholder:text-zinc-500 border-zinc-700/60 rounded-xl"
                  />
                )}
              </div>

              {/* URL */}
              <div className="space-y-2">
                <label htmlFor="creatorUrl" className="text-sm text-zinc-400">
                  Creator URL
                </label>
                <Input
                  type="url"
                  id="creatorUrl"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://tiktok.com/@username"
                  required
                  className="h-11 bg-zinc-900/60 text-zinc-100 placeholder:text-zinc-500 border-zinc-700/60 rounded-xl"
                />
              </div>

              {/* Submit */}
              <div className="flex justify-end">
                <Button
                  type="submit"
                  disabled={loading || !url.trim() || !senderProfile.trim()}
                  className="bg-white text-black hover:bg-white/90 rounded-full px-6 disabled:opacity-40"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <svg
                        className="h-4 w-4 animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                        />
                      </svg>
                      Processing…
                    </span>
                  ) : (
                    "Submit"
                  )}
                </Button>
              </div>
            </form>
          </div>
        </StyledCard>

        {/* Error */}
        {error && (
          <div className="mt-6">
            <StyledCard className="border-red-500/30">
              <div className="px-6 py-4">
                <p className="text-sm font-medium text-red-400">Error</p>
                <p className="mt-1 text-sm text-red-300/80">{error}</p>
              </div>
            </StyledCard>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="mt-8">
            <ResultCard result={result} copyText={copyText} copied={copied} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Result Card ────────────────────────────────────────────────────────────

function ResultCard({
  result,
  copyText,
  copied,
}: {
  result: ScrapeResponse;
  copyText: (text: string, label: string) => void;
  copied: string | null;
}) {
  const igHandle = (result as any).ig_handle as string | undefined;
  const igWebUrl = igHandle ? `https://instagram.com/${igHandle}` : null;

  const dmText = (result as any).dm_text as string | undefined;
  const emailTo = (result as any).email_to as string | undefined;
  const emailSubject = (result as any).email_subject as string | undefined;
  const emailBodyText = (result as any).email_body_text as string | undefined;
  const isFollowup = (result as any).is_followup as boolean | undefined;
  const sentFromEmail = (result as any).sent_from_email as string | undefined;
  const sentFromIg = (result as any).sent_from_ig as string | undefined;
  const sentFromTiktok = (result as any).sent_from_tiktok as string | undefined;

  const mailtoUrl =
    emailTo && emailSubject && emailBodyText
      ? `mailto:${emailTo}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBodyText)}`
      : null;

  console.log("Email Debug:", { emailTo, emailSubject, emailBodyText, mailtoUrl });

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-center text-xl sm:text-2xl text-zinc-100 font-medium">
        Results
      </h2>

      {/* Follow-up badge */}
      {isFollowup && (
        <StyledCard className="border-amber-500/30">
          <div className="px-6 py-3">
            <p className="text-sm font-medium text-amber-400">
              ⚠️ Follow-up — this creator was already contacted
            </p>
          </div>
        </StyledCard>
      )}

      {/* DM Text */}
      {dmText && (
        <StyledCard>
          <div className="px-6 py-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-400">
                DM Script
              </div>
              <CopyButton
                onClick={() => copyText(dmText, "dm")}
                active={copied === "dm"}
              />
            </div>
            <pre className="whitespace-pre-wrap rounded-xl bg-zinc-900/60 border border-zinc-700/60 p-4 text-sm leading-relaxed text-zinc-200">
              {dmText}
            </pre>
          </div>
        </StyledCard>
      )}

      {/* Raw Lead Success Message (No DM/Email) */}
      {!dmText && !emailBodyText && (result as any).message && (
        <StyledCard className="border-green-500/30">
          <div className="px-6 py-5">
            <h3 className="text-lg font-medium text-green-400 mb-2">Success</h3>
            <p className="text-zinc-300">{(result as any).message}</p>
            {(result as any).url && (
              <p className="text-zinc-500 text-sm mt-2">URL: {(result as any).url}</p>
            )}
          </div>
        </StyledCard>
      )}

      {/* Email */}
      {emailBodyText && (
        <StyledCard>
          <div className="px-6 py-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-400">
                Email
              </div>
              <CopyButton
                onClick={() => copyText(emailBodyText!, "email")}
                active={copied === "email"}
              />
            </div>
            {emailTo && (
              <p className="mb-1 text-xs text-zinc-500">
                To: <span className="text-zinc-300">{emailTo}</span>
              </p>
            )}
            {emailSubject && (
              <p className="mb-3 text-xs text-zinc-500">
                Subject:{" "}
                <span className="text-zinc-300">{emailSubject}</span>
              </p>
            )}
            <pre className="whitespace-pre-wrap rounded-xl bg-zinc-900/60 border border-zinc-700/60 p-4 text-sm leading-relaxed text-zinc-200">
              {emailBodyText}
            </pre>
            {mailtoUrl && (
              <a
                href={mailtoUrl}
                className="mt-4 inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-200 transition duration-500"
              >
                <MailIcon />
                Compose in email client →
              </a>
            )}
          </div>
        </StyledCard>
      )}

      {/* Instagram link */}
      {igWebUrl && (
        <StyledCard>
          <div className="px-6 py-5">
            <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-400 mb-4">
              Instagram
            </div>
            <a
              href={igWebUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 transition duration-500"
            >
              <IGIcon />
              @{igHandle} →
            </a>
          </div>
        </StyledCard>
      )}

      {/* Metadata */}
      <StyledCard>
        <div className="px-6 py-5">
          <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-400 mb-4">
            Details
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {sentFromEmail && (
              <div>
                <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-500">
                  Sent from
                </div>
                <div className="text-sm text-zinc-100 mt-1">
                  {sentFromEmail}
                </div>
              </div>
            )}
            {sentFromIg && (
              <div>
                <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-500">
                  IG Account
                </div>
                <div className="text-sm text-zinc-100 mt-1">
                  {sentFromIg}
                </div>
              </div>
            )}
            {sentFromTiktok && (
              <div>
                <div className="text-[10px] sm:text-xs uppercase tracking-wide text-zinc-500">
                  TikTok Account
                </div>
                <div className="text-sm text-zinc-100 mt-1">
                  {sentFromTiktok}
                </div>
              </div>
            )}
          </div>
        </div>
      </StyledCard>
    </div>
  );
}

// ── Mini-components ────────────────────────────────────────────────────────

function CopyButton({
  onClick,
  active,
}: {
  onClick: () => void;
  active: boolean;
}) {
  return (
    <Button
      type="button"
      onClick={onClick}
      variant="outline"
      size="sm"
      className={cn(
        "rounded-full border-zinc-700/60 bg-zinc-900/60 text-zinc-400 hover:border-zinc-500/60 hover:text-zinc-200 hover:bg-zinc-800/60",
        active &&
        "border-green-500/40 bg-green-500/10 text-green-400 hover:bg-green-500/10 hover:text-green-400 hover:border-green-500/40"
      )}
    >
      {active ? "✓ Copied" : "Copy"}
    </Button>
  );
}

function MailIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}

function IGIcon() {
  return (
    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162S8.597 18.163 12 18.163s6.162-2.759 6.162-6.162S15.403 5.838 12 5.838zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
    </svg>
  );
}
