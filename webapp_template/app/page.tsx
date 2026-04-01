"use client";
import { useState } from "react";

const APP_NAME = "__APP_NAME__";
const TAGLINE = "__TAGLINE__";
const DESCRIPTION = "__DESCRIPTION__";
const FEATURES = [
  { icon: "⚡", name: "__FEATURE_1_NAME__", desc: "__FEATURE_1_DESC__" },
  { icon: "🎯", name: "__FEATURE_2_NAME__", desc: "__FEATURE_2_DESC__" },
  { icon: "🚀", name: "__FEATURE_3_NAME__", desc: "__FEATURE_3_DESC__" },
];
const PRICE_MONTHLY = __PRICE_MONTHLY__;
const PRICE_YEARLY = __PRICE_YEARLY__;

export default function Home() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [yearly, setYearly] = useState(false);
  const [error, setError] = useState("");

  const handleCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, yearly }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError("Payment unavailable. Try again shortly.");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="sticky top-0 z-10 bg-white border-b px-6 py-4 flex justify-between items-center">
        <span className="text-xl font-bold text-indigo-600">{APP_NAME}</span>
        <a
          href="#pricing"
          className="text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors"
        >
          Pricing
        </a>
      </nav>

      {/* Hero */}
      <section className="py-24 px-6 text-center">
        <div className="max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 text-sm font-medium px-4 py-1.5 rounded-full mb-8">
            <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
            Now live — join early access
          </div>
          <h1 className="text-5xl sm:text-6xl font-extrabold text-gray-900 leading-tight mb-6">
            {TAGLINE}
          </h1>
          <p className="text-xl text-gray-500 mb-8 leading-relaxed">{DESCRIPTION}</p>

          <div className="mb-6">
            <a
              href="/tool"
              className="inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl px-8 py-3 text-base transition-colors"
            >
              Try it free →
            </a>
            <p className="mt-2 text-sm text-gray-400">No sign-up needed · 3 free uses</p>
          </div>

          <form onSubmit={handleCheckout} className="flex flex-col sm:flex-row gap-3 justify-center">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="border border-gray-300 rounded-xl px-5 py-3 text-base w-full sm:w-72 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold rounded-xl px-8 py-3 text-base transition-colors whitespace-nowrap"
            >
              {loading ? "Redirecting…" : "Get started →"}
            </button>
          </form>
          {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
          <p className="mt-4 text-sm text-gray-400">
            No credit card needed to sign up. Cancel anytime.
          </p>
        </div>
      </section>

      {/* Social proof */}
      <section className="py-8 px-6 bg-gray-50 border-y text-center">
        <p className="text-sm text-gray-500 font-medium">
          Trusted by founders, freelancers &amp; creators worldwide
        </p>
      </section>

      {/* Features */}
      <section className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center text-gray-900 mb-4">
            Everything you need
          </h2>
          <p className="text-center text-gray-500 mb-16 text-lg">
            Built to solve the exact problem. No fluff.
          </p>
          <div className="grid sm:grid-cols-3 gap-8">
            {FEATURES.map((f, i) => (
              <div
                key={i}
                className="bg-white border border-gray-100 rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="text-4xl mb-4">{f.icon}</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{f.name}</h3>
                <p className="text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6 bg-gray-50">
        <div className="max-w-md mx-auto text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Simple, honest pricing</h2>
          <p className="text-gray-500 mb-10">One plan. All features. No surprises.</p>

          {/* Toggle */}
          <div className="flex items-center justify-center gap-3 mb-10">
            <span className={`text-sm font-medium ${!yearly ? "text-gray-900" : "text-gray-400"}`}>
              Monthly
            </span>
            <button
              onClick={() => setYearly(!yearly)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                yearly ? "bg-indigo-600" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                  yearly ? "translate-x-6" : ""
                }`}
              />
            </button>
            <span className={`text-sm font-medium ${yearly ? "text-gray-900" : "text-gray-400"}`}>
              Yearly{" "}
              <span className="text-green-600 font-semibold">Save 30%</span>
            </span>
          </div>

          <div className="bg-white border-2 border-indigo-200 rounded-2xl p-8 shadow-sm">
            <div className="text-6xl font-extrabold text-indigo-600 mb-1">
              ${yearly ? PRICE_YEARLY : PRICE_MONTHLY}
            </div>
            <div className="text-gray-400 text-sm mb-6">{yearly ? "per year" : "per month"}</div>

            <ul className="text-left space-y-3 mb-8">
              {FEATURES.map((f, i) => (
                <li key={i} className="flex items-start gap-3 text-gray-700">
                  <span className="text-green-500 font-bold mt-0.5">✓</span>
                  <span>
                    <strong>{f.name}</strong> — {f.desc}
                  </span>
                </li>
              ))}
              <li className="flex items-center gap-3 text-gray-700">
                <span className="text-green-500 font-bold">✓</span> Email support
              </li>
              <li className="flex items-center gap-3 text-gray-700">
                <span className="text-green-500 font-bold">✓</span> Cancel anytime
              </li>
            </ul>

            <form onSubmit={handleCheckout}>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full border border-gray-300 rounded-xl px-4 py-3 mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold rounded-xl py-3 transition-colors text-base"
              >
                {loading ? "Processing…" : "Start now →"}
              </button>
            </form>
            {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t text-center text-sm text-gray-400">
        <p>
          © 2025 {APP_NAME}. All rights reserved. · Payments secured by{" "}
          <span className="font-medium text-gray-500">Dodo Payments</span>
        </p>
      </footer>
    </div>
  );
}
