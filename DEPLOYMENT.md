# Deploying the repaired application

Use this repository root (`code-review-agent/`), not the untracked nested
`ai-code-review-agent/` snapshot. No API secrets need to be committed.

## Render backend

- Service: the Python backend, not the Node frontend service.
- Build: `pip install -r requirements.txt`
- Start: `python -m uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1`
- Configure `GOOGLE_API_KEY` and `GEMINI_MODEL` privately in Render.
- Health-check path: `/health`.
- Keep `ALLOW_LOCAL_REPOSITORIES` unset/false for public hosting. Set it to
  `true` only for trusted local development where filesystem access is intended.
- Verify Git is available in the runtime. The backend Dockerfile includes Git.

This version uses embedded Qdrant and in-process background jobs. Run one worker
and one backend instance. Jobs are lost on restart; rerun analysis after a restart.
Persist both `qdrant_storage/` and `repository_cache.db` together if the hosting
plan supports persistent storage. Otherwise expect reindexing after redeployment.
The cache now checks that its vector collection exists and matches the recorded
count before reuse.

## Vercel frontend

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Set `VITE_API_URL` to the actual Python backend's HTTPS origin (no `/index` suffix).
- Apply the variable to Production and any Preview environments that need it.
- Rebuild/redeploy after changing the variable. Vite embeds it during the build.

The previous live frontend called a Railway backend even though the local code
had a Render fallback. A Vercel environment variable takes priority over that
fallback. Do not assume editing the fallback updates an existing deployment.

The current backend CORS list includes the production Vercel domain. Add exact
additional frontend origins when deploying previews/custom domains.

## Verification

1. Open `<backend-origin>/health`; expect `{"status":"ok"}`.
2. Load the frontend; confirm its health badge changes to “Backend online”.
3. Analyze a small public Python repository; wait for completion.
4. Generate an overview and ask a question; both should display answers.
5. Confirm browser requests go to the intended backend.

The health badge checks API availability, not Gemini credentials or quota.
The application currently indexes Python and selected Markdown, including Python
tests, up to 120 chunks. It does not yet index TypeScript/JavaScript source.

Repository IDs now include the owner and a hash. Old indexes are not reused;
reanalyze repositories once after deploying this version.

## Local checks

- `venv/bin/python -m pytest -q`
- `cd frontend && npm run build`

The test suite mocks generation; it does not use Gemini quota. Two existing
clone tests require network access to GitHub.

## Streaming and response cache

The frontend uses `/ask/stream` and `/project/overview/stream` for progressive
answers. The JSON endpoints remain available for existing clients. Deploy the
backend before the updated frontend so streaming routes exist when it switches.

Completed model responses are cached for 24 hours, capped at 1,000 entries, in
`answer_cache.db`. Keys include the full grounded prompt (question, mode and
retrieved content), model, prompt version, repository collection and recorded
commit/index version. Partial, failed and cancelled generations are not cached.
Retrieval still runs before cache lookup, so changed retrieved code invalidates
answers even for trusted local repositories without a Git revision.

Optional non-secret path settings:

- `REPOSITORY_CACHE_PATH`: SQLite repository metadata file.
- `ANSWER_CACHE_PATH`: SQLite answer cache file.

These paths alone do not make Render's free disk durable. Free external durable
storage still needs to be configured in a subsequent change. No paid resource
or external account is provisioned by this patch.

Unchanged repositories now check remote HEAD with `git ls-remote` and reuse a
verified index without cloning. If that check fails, the normal clone path is
used. Changed repositories still rebuild their index; incremental indexing is
not implemented here.

Tests force `LOAD_DOTENV=false`, dummy model credentials, and temporary SQLite
paths. To build the frontend without loading any `.env` files, also set
`LOAD_DOTENV=false`. Run `npm run test:stream` from `frontend/` to verify the
stream parser's split frames, Unicode and interruption handling.
