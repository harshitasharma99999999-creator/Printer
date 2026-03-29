export default function Success() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="text-center max-w-md">
        <div className="text-7xl mb-6">🎉</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Payment successful!</h1>
        <p className="text-gray-500 mb-8 leading-relaxed">
          Thank you for your purchase. Check your inbox — we&apos;ll send your access
          details within a few minutes.
        </p>
        <a
          href="/"
          className="inline-flex items-center gap-2 text-indigo-600 hover:underline font-medium"
        >
          ← Back to home
        </a>
      </div>
    </div>
  );
}
