export default function PrivacyPolicy() {
  const appName = process.env.NEXT_PUBLIC_APP_NAME || "This App";
  const contact = "harshitasharma99999999@gmail.com";
  const date = "April 2026";

  return (
    <main className="max-w-3xl mx-auto px-6 py-16 text-gray-800">
      <h1 className="text-3xl font-bold mb-2">{appName} — Privacy Policy</h1>
      <p className="text-sm text-gray-500 mb-10">Last updated: {date}</p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">1. Information We Collect</h2>
        <p>
          {appName} does not collect, store, or sell any personal information.
          When you use the AI generation tool, your input is sent to our AI provider
          (Google Gemini) solely to generate your requested content and is not stored.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">2. Payment Information</h2>
        <p>
          Payments are processed securely by Dodo Payments. We never see or store
          your card details. All transactions are encrypted and handled by our payment provider.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">3. Cookies</h2>
        <p>
          We use minimal, strictly necessary cookies only — no tracking or advertising cookies.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">4. Third-Party Services</h2>
        <p>
          We use Google Gemini API for AI content generation. Please refer to
          Google&apos;s privacy policy for how they handle API requests.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">5. Data Retention</h2>
        <p>
          We do not retain any user-generated content or personal data beyond the
          duration of a single session.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">6. Children&apos;s Privacy</h2>
        <p>
          This app is not directed at children under 13. We do not knowingly collect
          any data from children.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-2">7. Contact Us</h2>
        <p>
          For any privacy questions, contact us at:{" "}
          <a href={`mailto:${contact}`} className="text-purple-600 underline">
            {contact}
          </a>
        </p>
      </section>
    </main>
  );
}
