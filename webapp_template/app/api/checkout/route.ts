import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { email } = await req.json();

    const apiKey = process.env.DODO_API_KEY;
    const productId = process.env.DODO_PRODUCT_ID;
    const baseUrl =
      process.env.NEXT_PUBLIC_BASE_URL ||
      `https://${req.headers.get("host")}`;

    if (!apiKey || !productId) {
      console.error("DODO_API_KEY or DODO_PRODUCT_ID not configured");
      return NextResponse.json(
        { error: "Payment not configured" },
        { status: 500 }
      );
    }

    const response = await fetch("https://api.dodopayments.com/payments", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        billing: { email },
        product_cart: [{ product_id: productId, quantity: 1 }],
        payment_link: true,
        return_url: `${baseUrl}/success`,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("Dodo Payments API error:", errText);
      return NextResponse.json(
        { error: "Payment creation failed" },
        { status: 502 }
      );
    }

    const data = await response.json();
    return NextResponse.json({ url: data.payment_link });
  } catch (err) {
    console.error("Checkout error:", err);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
