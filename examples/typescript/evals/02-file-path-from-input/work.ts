import { readFile } from "node:fs/promises";
import path from "node:path";

interface Session {
  userId: string;
}

interface DownloadRequest {
  session: Session | null;
  params: { name: string };
}

interface Reply {
  status: number;
  headers?: Record<string, string>;
  body: unknown;
}

const UPLOADS = "/var/app/uploads";

// GET /attachments/:name: sends back a file the signed-in user uploaded earlier.
// Each user's files live in their own folder under UPLOADS.
export async function serveAttachment(req: DownloadRequest): Promise<Reply> {
  if (!req.session) return { status: 401, body: { error: "sign in first" } };
  const name = decodeURIComponent(req.params.name);
  const file = path.join(UPLOADS, req.session.userId, name);
  try {
    const data = await readFile(file);
    return {
      status: 200,
      headers: { "content-type": "application/octet-stream", "content-disposition": "attachment" },
      body: data,
    };
  } catch {
    return { status: 404, body: { error: "no such file" } };
  }
}
