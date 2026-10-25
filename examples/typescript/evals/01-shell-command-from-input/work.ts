import { exec } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(exec);

interface Session {
  userId: string;
}

interface ExportRequest {
  session: Session | null;
  body: { reportId?: string; title?: string; format?: string };
}

interface Reply {
  status: number;
  body: unknown;
}

interface Reports {
  ownedBy(reportId: string, userId: string): Promise<boolean>;
}

const FORMATS = new Set(["csv", "pdf"]);
const EXPORTS = "/var/app/exports";

// POST /reports/export: renders a saved report to a file the user can download.
// The title is free text the user types; it goes on the first page.
export async function runReportExport(req: ExportRequest, reports: Reports): Promise<Reply> {
  if (!req.session) return { status: 401, body: { error: "sign in first" } };
  const { reportId, title = "Report", format = "csv" } = req.body;
  if (!reportId || !/^[0-9]+$/.test(reportId) || !FORMATS.has(format)) {
    return { status: 400, body: { error: "bad request" } };
  }
  if (!(await reports.ownedBy(reportId, req.session.userId))) {
    return { status: 404, body: { error: "no such report" } };
  }
  const out = `${EXPORTS}/${req.session.userId}-${reportId}.${format}`;
  await run(`report-render --id ${reportId} --format ${format} --title "${title}" --out ${out}`);
  return { status: 200, body: { file: `/downloads/${req.session.userId}-${reportId}.${format}` } };
}
