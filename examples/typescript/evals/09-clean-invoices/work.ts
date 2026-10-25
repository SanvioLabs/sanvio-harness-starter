interface Session {
  userId: string;
  accountId: string;
}

interface InvoiceRequest {
  session: Session | null;
  params: { id?: string };
  query: { q?: string };
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

const COLUMNS = "id, number, customer_name, total_cents";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

// GET /invoices?q=acme: the account's invoices, filtered by customer name, newest first.
export async function listInvoices(db: Db, req: InvoiceRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const q = (req.query.q ?? "").trim().slice(0, 100).replace(/[\\%_]/g, (c) => "\\" + c);
  const rows = await db.query<Invoice>(
    `select ${COLUMNS} from invoices where account_id = $1 and customer_name ilike '%' || $2 || '%' ` +
      "order by issued_at desc limit 50",
    [req.session.accountId, q],
  );
  return { status: 200, body: rows };
}

// GET /invoices/:id: one invoice, only if it belongs to the caller's account.
export async function showInvoice(db: Db, req: InvoiceRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  if (!req.params.id || !UUID.test(req.params.id)) return { status: 404 };
  const rows = await db.query<Invoice>(
    `select ${COLUMNS} from invoices where id = $1 and account_id = $2`,
    [req.params.id, req.session.accountId],
  );
  return rows.length ? { status: 200, body: rows[0] } : { status: 404 };
}
