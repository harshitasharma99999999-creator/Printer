import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    ok: true,
    env: {
      geminiConfigured: Boolean(process.env.GEMINI_API_KEY),
      dodoConfigured: Boolean(process.env.DODO_API_KEY && process.env.DODO_PRODUCT_ID),
      baseUrlConfigured: Boolean(process.env.NEXT_PUBLIC_BASE_URL),
    },
  });
}
