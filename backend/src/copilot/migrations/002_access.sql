-- Who may read what is enforced by Postgres, before any paragraph reaches ranking or a model.
-- Each request runs in a transaction that sets app.login, app.clearance and app.groups from the
-- users table (copilot.db.as_user); ingestion and evaluation set app.system. A connection that
-- sets neither sees nothing.

CREATE FUNCTION app_login() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.login', true), '')
$$;
CREATE FUNCTION app_clearance() RETURNS int LANGUAGE sql STABLE AS $$
  SELECT coalesce(nullif(current_setting('app.clearance', true), '')::int, 0)
$$;
CREATE FUNCTION app_groups() RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT coalesce(string_to_array(nullif(current_setting('app.groups', true), ''), ','), '{}')
$$;
CREATE FUNCTION app_system() RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT coalesce(current_setting('app.system', true), '') = 'on'
$$;
CREATE FUNCTION app_reviewer() RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT app_groups() && ARRAY['copilot-reviewer', 'audit-all']
$$;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self ON users USING (app_system() OR login = app_login());

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY documents_read ON documents
  USING (app_system() OR (classification <= app_clearance() AND read_groups && app_groups()))
  WITH CHECK (app_system());

ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY versions_read ON document_versions
  USING (app_system() OR EXISTS (SELECT 1 FROM documents d WHERE d.id = document_id))
  WITH CHECK (app_system());

ALTER TABLE paragraphs ENABLE ROW LEVEL SECURITY;
ALTER TABLE paragraphs FORCE ROW LEVEL SECURITY;
CREATE POLICY paragraphs_read ON paragraphs
  USING (app_system() OR (classification <= app_clearance() AND read_groups && app_groups()))
  WITH CHECK (app_system());

ALTER TABLE queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE queries FORCE ROW LEVEL SECURITY;
CREATE POLICY queries_read ON queries FOR SELECT USING (app_system() OR login = app_login() OR app_reviewer());
CREATE POLICY queries_write ON queries FOR INSERT WITH CHECK (app_system() OR login = app_login());

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback FORCE ROW LEVEL SECURITY;
CREATE POLICY feedback_read ON feedback FOR SELECT USING (app_system() OR login = app_login() OR app_reviewer());
CREATE POLICY feedback_write ON feedback FOR INSERT WITH CHECK (login = app_login());
CREATE POLICY feedback_resolve ON feedback FOR UPDATE USING (app_reviewer()) WITH CHECK (app_reviewer());

ALTER TABLE impact_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE impact_items FORCE ROW LEVEL SECURITY;
CREATE POLICY impact_read ON impact_items FOR SELECT
  USING (app_system() OR EXISTS (SELECT 1 FROM paragraphs p WHERE p.id = paragraph_id));
CREATE POLICY impact_write ON impact_items FOR INSERT WITH CHECK (app_system());
CREATE POLICY impact_resolve ON impact_items FOR UPDATE
  USING (app_system() OR (app_reviewer() AND EXISTS (SELECT 1 FROM paragraphs p WHERE p.id = paragraph_id)));

ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY runs_all ON ingestion_runs USING (app_system() OR app_reviewer()) WITH CHECK (app_system());

-- The audit chain needs the latest hash regardless of who asked last; nothing else is exposed.
CREATE FUNCTION last_query_hash() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce((SELECT hash FROM queries ORDER BY id DESC LIMIT 1), 'genesis')
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'copilot_app') THEN
    CREATE ROLE copilot_app LOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO copilot_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO copilot_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO copilot_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO copilot_app;
REVOKE UPDATE ON queries FROM copilot_app;  -- the audit trail is append-only for the app
