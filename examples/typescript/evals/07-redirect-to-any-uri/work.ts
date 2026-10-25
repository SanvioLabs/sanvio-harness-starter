import { randomBytes } from "node:crypto";

interface Session {
  userId: string;
}

interface AuthorizeRequest {
  session: Session | null;
  query: { client_id?: string; redirect_uri?: string; state?: string };
}

interface Reply {
  status: number;
  headers?: Record<string, string>;
  body?: unknown;
}

interface Clients {
  // The redirect URIs each partner app registered with us.
  registeredUris(clientId: string): Promise<string[] | null>;
}

interface Codes {
  // A code the partner app trades for access to this user's account, valid ten minutes.
  save(code: string, userId: string, clientId: string): Promise<void>;
}

// GET /oauth/authorize: the user has approved a partner app; send them back to it with a code.
export async function issueAuthCode(req: AuthorizeRequest, clients: Clients, codes: Codes): Promise<Reply> {
  if (!req.session) return { status: 302, headers: { location: "/signin" } };
  const { client_id, redirect_uri, state = "" } = req.query;
  if (!client_id || !redirect_uri) return { status: 400, body: { error: "missing parameters" } };
  const uris = await clients.registeredUris(client_id);
  if (!uris) return { status: 400, body: { error: "unknown client" } };
  const code = randomBytes(32).toString("hex");
  await codes.save(code, req.session.userId, client_id);
  const back = new URL(redirect_uri);
  back.searchParams.set("code", code);
  back.searchParams.set("state", state);
  return { status: 302, headers: { location: back.href } };
}
