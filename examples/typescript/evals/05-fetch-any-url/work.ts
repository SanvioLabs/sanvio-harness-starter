interface Session {
  userId: string;
}

interface PreviewRequest {
  session: Session | null;
  body: { url?: string };
}

interface Reply {
  status: number;
  body?: unknown;
}

const TITLE = /<title[^>]*>([^<]*)<\/title>/i;

// POST /previews: a user pastes a link into a comment, and the server fetches the page
// to show its title and an excerpt in a link card. Runs on the app servers, inside the VPC.
export async function fetchLinkPreview(req: PreviewRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  let target: URL;
  try {
    target = new URL(req.body.url ?? "");
  } catch {
    return { status: 400, body: { error: "not a link" } };
  }
  if (target.protocol !== "http:" && target.protocol !== "https:") {
    return { status: 400, body: { error: "only web links" } };
  }
  const page = await fetch(target, { redirect: "follow", signal: AbortSignal.timeout(5000) });
  const html = await page.text();
  return {
    status: 200,
    body: {
      url: target.href,
      status: page.status,
      title: TITLE.exec(html)?.[1]?.trim() ?? target.hostname,
      excerpt: html.slice(0, 500),
    },
  };
}
