"use client";
import { useState, useEffect } from "react";

const APP_NAME = "__APP_NAME__";
const TOOL_TITLE = "__TOOL_TITLE__";
const TOOL_DESCRIPTION = "__TOOL_DESCRIPTION__";
const INPUT_1_LABEL = "__INPUT_1_LABEL__";
const INPUT_1_PLACEHOLDER = "__INPUT_1_PLACEHOLDER__";
const INPUT_2_LABEL = "__INPUT_2_LABEL__";
const INPUT_2_PLACEHOLDER = "__INPUT_2_PLACEHOLDER__";
const OUTPUT_LABEL = "__OUTPUT_LABEL__";
const FREE_LIMIT = 3;
const STORAGE_KEY = "mpv2_uses";

export default function ToolPage() {
  const [input1, setInput1] = useState("");
  const [input2, setInput2] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [usesLeft, setUsesLeft] = useState(FREE_LIMIT);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const used = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);
    setUsesLeft(Math.max(0, FREE_LIMIT - used));
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input1.trim()) return;

    const used = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);
    if (used >= FREE_LIMIT) {
      setError("You've used all free generations. Upgrade to continue.");
      return;
    }

    setLoading(true);
    setError("");
    setResult("");

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input1: input1.trim(), input2: input2.trim() }),
      });
      const data = await res.json();
      if (data.result) {
        const newUsed = used + 1;
        localStorage.setItem(STORAGE_KEY, String(newUsed));
        setUsesLeft(Math.max(0, FREE_LIMIT - newUsed));
        setResult(data.result);
      } else {
        setError(data.error || "Generation failed. Please try again.");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    }
    setLoading(false);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isLocked = usesLeft === 0 && !result;
  const showPaywall = usesLeft === 0 && result;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-white border-b px-6 py-4 flex justify-between items-center">
        <a href="/" className="text-xl font-bold text-indigo-600">{APP_NAME}</a>
        <a
          href="/#pricing"
          className="text-sm font-semibold bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Upgrade →
        </a>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-3">{TOOL_TITLE}</h1>
          <p className="text-gray-500 text-lg">{TOOL_DESCRIPTION}</p>
          {usesLeft > 0 && (
            <p className="mt-3 text-sm text-indigo-600 font-medium">
              {usesLeft} free generation{usesLeft !== 1 ? "s" : ""} remaining
            </p>
          )}
        </div>

        {/* Form */}
        <form onSubmit={handleGenerate} className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">{INPUT_1_LABEL}</label>
            <textarea
              value={input1}
              onChange={(e) => setInput1(e.target.value)}
              placeholder={INPUT_1_PLACEHOLDER}
              required
              rows={3}
              disabled={isLocked}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">{INPUT_2_LABEL}</label>
            <textarea
              value={input2}
              onChange={(e) => setInput2(e.target.value)}
              placeholder={INPUT_2_PLACEHOLDER}
              rows={3}
              disabled={isLocked}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          {isLocked ? (
            <a
              href="/#pricing"
              className="block w-full text-center bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl py-3 text-base transition-colors"
            >
              Unlock unlimited generations →
            </a>
          ) : (
            <button
              type="submit"
              disabled={loading || !input1.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold rounded-xl py-3 text-base transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Generating…
                </>
              ) : (
                "Generate →"
              )}
            </button>
          )}

          {error && <p className="text-sm text-red-500 text-center">{error}</p>}
        </form>

        {/* Output */}
        {result && (
          <div className="mt-6 bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold text-gray-700">{OUTPUT_LABEL}</h2>
              <button
                onClick={handleCopy}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
              >
                {copied ? "✓ Copied!" : "Copy"}
              </button>
            </div>
            <div className={`relative ${showPaywall ? "select-none" : ""}`}>
              <pre className={`whitespace-pre-wrap text-gray-800 text-sm leading-relaxed font-sans ${showPaywall ? "blur-sm pointer-events-none" : ""}`}>
                {result}
              </pre>
              {showPaywall && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 rounded-xl">
                  <p className="text-gray-900 font-semibold mb-3">You've used all free generations</p>
                  <a
                    href="/#pricing"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl px-6 py-2.5 text-sm transition-colors"
                  >
                    Unlock unlimited →
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer nudge */}
        {!result && !isLocked && (
          <p className="text-center text-sm text-gray-400 mt-8">
            Want unlimited generations?{" "}
            <a href="/#pricing" className="text-indigo-600 hover:underline font-medium">
              See pricing
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
