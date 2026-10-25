interface Session {
  userId: string;
}

interface ProjectRequest {
  session: Session | null;
  params: { id: string };
}

interface Reply {
  status: number;
  body?: unknown;
}

interface Db {
  query<T>(text: string, values?: unknown[]): Promise<T[]>;
}

interface Project {
  id: string;
  name: string;
  owner_id: string;
}

// GET /projects/:id: one of the signed-in user's projects.
export async function showProject(db: Db, req: ProjectRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const rows = await db.query<Project>(
    "select id, name, owner_id from projects where id = $1 and owner_id = $2",
    [req.params.id, req.session.userId],
  );
  return rows.length ? { status: 200, body: rows[0] } : { status: 404 };
}

// DELETE /projects/:id: removes a project and everything in it.
export async function removeProject(db: Db, req: ProjectRequest): Promise<Reply> {
  if (!req.session) return { status: 401 };
  const rows = await db.query<Project>("select id, name, owner_id from projects where id = $1", [req.params.id]);
  if (!rows.length) return { status: 404 };
  await db.query("delete from tasks where project_id = $1", [req.params.id]);
  await db.query("delete from projects where id = $1", [req.params.id]);
  return { status: 204 };
}
