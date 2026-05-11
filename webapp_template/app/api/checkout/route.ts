import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { email } = await req.json();

    const apiKey = process.env.DODO_API_KEY;
    const productId = process.env.DODO_PRODUCT_ID;
    const dodoBaseUrl =
      process.env.DODO_BASE_URL || "https://live.dodopayments.com";
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

    const response = await fetch(`${dodoBaseUrl}/checkouts`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        customer: { email },
        product_cart: [{ product_id: productId, quantity: 1 }],
        return_url: `${baseUrl}/success`,
        allowed_payment_method_types: ["credit", "debit"],
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("Dodo Payments API error:", errText);
      return NextResponse.json(
        { error: "Payment creation failed", detail: errText.slice(0, 500) },
        { status: 502 }
      );
    }

    const data = await response.json();
    return NextResponse.json({
      url: data.checkout_url || data.payment_link,
    });
  } catch (err) {
    console.error("Checkout error:", err);
    return NextResponse.json(
      { error: "Internal error", detail: String(err) },
      { status: 500 }
    );
  }
}
