import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

interface Session {
  userId: string;
}

interface ExportRequest {
  session: Session | null;
  params: { reportId?: string; format?: string };
}

interface Reply {
  status: number;
  headers?: Record<string, string>;
  body?: unknown;
}

interface Reports {
  ownedBy(reportId: string, userId: string): Promise<boolean>;
}

const FORMATS = new Set(["csv", "pdf"]);
const EXPORTS = path.resolve("/var/app/exports");

// GET /reports/:reportId/export.:format: renders one of the caller's reports and sends it back.
export async function exportReport(req: ExportRequest, reports: Reports): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const { reportId = "", format = "" } = req.params;
  if (!/^[0-9]{1,12}$/.test(reportId) || !FORMATS.has(format)) return { status: 404 };
  if (!(await reports.ownedBy(reportId, req.session.userId))) return { status: 404 };
  const out = path.resolve(EXPORTS, `${reportId}.${format}`);
  if (path.dirname(out) !== EXPORTS) return { status: 404 };
  // execFile passes each argument as-is, with no shell to read them.
  await run("report-render", ["--id", reportId, "--format", format, "--out", out], { timeout: 30_000 });
  return {
    status: 200,
    headers: { "content-type": format === "pdf" ? "application/pdf" : "text/csv", "content-disposition": "attachment" },
    body: await readFile(out),
  };
}
