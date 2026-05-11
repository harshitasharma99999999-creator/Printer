import { NextRequest, NextResponse } from "next/server";

const TOOL_PROMPT = `__TOOL_PROMPT__`;

export async function POST(req: NextRequest) {
  try {
    const { input1, input2 } = await req.json();

    if (!input1?.trim()) {
      return NextResponse.json({ error: "Input is required" }, { status: 400 });
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ error: "Service not configured" }, { status: 500 });
    }

    const prompt = TOOL_PROMPT
      .replace(/\{input1\}/g, input1.trim())
      .replace(/\{input2\}/g, (input2 || "").trim());

    const response = await fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": apiKey,
        },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.8, maxOutputTokens: 1024 },
        }),
      }
    );

    if (!response.ok) {
      const errText = await response.text();
      console.error("Gemini API error:", errText);
      return NextResponse.json({ error: "Generation failed" }, { status: 502 });
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!text) {
      return NextResponse.json({ error: "No result generated" }, { status: 500 });
    }

    return NextResponse.json({ result: text });
  } catch (err) {
    console.error("Generate error:", err);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
