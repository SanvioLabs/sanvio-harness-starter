interface Session {
  userId: string;
  shopId: string;
}

interface QuoteRequest {
  session: Session | null;
  body: { items?: { sku: string; qty: number }[] };
}

interface Reply {
  status: number;
  body?: unknown;
}

interface Shops {
  // Each merchant writes their own pricing formula in the shop settings page,
  // such as "price * qty * (qty >= 10 ? 0.9 : 1)". Every shop runs on the same servers.
  pricingFormula(shopId: string): Promise<string>;
  unitPrice(shopId: string, sku: string): Promise<number | null>;
}

// POST /quotes: prices a cart with the shop's own formula.
export async function applyPricingFormula(req: QuoteRequest, shops: Shops): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const items = req.body.items ?? [];
  if (!items.length || items.some((i) => !Number.isInteger(i.qty) || i.qty < 1)) {
    return { status: 400, body: { error: "bad cart" } };
  }
  const formula = await shops.pricingFormula(req.session.shopId);
  const price = new Function("price", "qty", "return " + formula) as (price: number, qty: number) => number;
  let total = 0;
  for (const item of items) {
    const unit = await shops.unitPrice(req.session.shopId, item.sku);
    if (unit === null) return { status: 400, body: { error: "unknown item " + item.sku } };
    total += price(unit, item.qty);
  }
  return { status: 200, body: { total: Math.round(total * 100) / 100 } };
}
