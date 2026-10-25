interface Session {
  userId: string;
  accountId: string;
}

interface SearchRequest {
  session: Session | null;
  query: { q?: string; page?: string };
}

interface Reply {
  status: number;
  body?: unknown;
}

interface Db {
  query<T>(text: string, values?: unknown[]): Promise<T[]>;
}

interface Invoice {
  id: string;
  number: string;
  customer_name: string;
  total_cents: number;
}

const PAGE_SIZE = 25;

// GET /invoices/search?q=acme&page=2: the account's invoices whose customer name matches q.
export async function searchInvoices(db: Db, req: SearchRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const q = (req.query.q ?? "").trim();
  const page = Math.max(1, Number.parseInt(req.query.page ?? "1", 10) || 1);
  if (q.length < 2) return { status: 400, body: { error: "type at least two letters" } };
  const rows = await db.query<Invoice>(
    "select id, number, customer_name, total_cents from invoices " +
      "where account_id = $1 and customer_name ilike '%" + q + "%' " +
      "order by issued_at desc limit $2 offset $3",
    [req.session.accountId, PAGE_SIZE, (page - 1) * PAGE_SIZE],
  );
  return { status: 200, body: { page, invoices: rows } };
}
