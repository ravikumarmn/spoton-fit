# Deployment (optional): Cloud Run + Neon

You do **not** need any of this to run or develop SpotOn; see the [README](../README.md) for running it locally.
This page describes the pipeline in `.github/workflows/deploy.yml`, which deploys to Google Cloud Run with a Neon
Postgres database. It is **off** until you set the repository variable `DEPLOY_ENABLED=true`, so forks never deploy.

## What happens on every push to `main`

CI (lint, tests, migrations check, offline evals, mobile tests) must pass. Then **Deploy** runs:

1. Build the Docker image and push it to Artifact Registry (tagged with the git SHA).
2. Run database migrations against Postgres (`python -m spotonfit.migrations`).
3. Deploy the image to Cloud Run and smoke-test `/readyz`.
4. Deploy the weekly-review Cloud Run Job (`spotonfit-weekly`; unscheduled, see below).
5. Build a signed Android APK that points at the new server, publish it as a GitHub Release (`app-v1.0.<run>`) and
   copy it to `gs://<project>-downloads/SpotOn.apk` (the bucket must exist and be publicly readable if you want a
   stable download link).

## One-time setup

**GitHub repository variables:** `DEPLOY_ENABLED`, `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_AR_REPO`,
`CLOUD_RUN_SERVICE`, `RUNTIME_SERVICE_ACCOUNT`.

**GitHub repository secrets:** `GCP_WIF_PROVIDER` and `GCP_SERVICE_ACCOUNT` (Workload Identity Federation, so there
are no long-lived JSON keys), and `ANDROID_KEYSTORE_B64` and `ANDROID_KEYSTORE_PASSWORD` (the release signing key).

**Google Secret Manager** (read by Cloud Run at runtime; never stored in GitHub):

| Secret | Holds |
| --- | --- |
| `spotonfit-jwt-secret` | `JWT_SECRET`, a long random string |
| `spotonfit-google-api-key` | `GOOGLE_API_KEY` for Gemini |
| `spotonfit-database-url` | the Postgres connection URL |

Give the runtime service account access to those three secrets and nothing else.

## Notes

- **Use the direct (not pooled) Neon URL.** asyncpg and psycopg use prepared statements, which PgBouncer's
  transaction pooling can break. One instance with small pools stays far below Neon's connection limit.
- **One instance, one process.** Rate limits are counted in memory, so the service runs `--max-instances=1` with one
  worker. Raise this only after moving the counters to Postgres or Redis.
- **Change a secret:** add a new version (`printf '%s' "$NEW" | gcloud secrets versions add <name> --data-file=-`),
  then re-run the Deploy workflow.
- **Weekly review job:** deployed but not scheduled. Reviews are also created when a user opens Progress. Schedule
  `spotonfit-weekly` with Cloud Scheduler if you want them generated ahead of time.
- **Release APK locally:** `flutter build apk --release --dart-define=SPOTON_API_URL=<your https URL>` in `mobile/`
  (reads `mobile/android/key.properties`, which is git-ignored). Release builds only talk to the built-in address and
  require `https://`.
- **Keep the Android signing key safe and backed up.** Android refuses updates signed with a different key.
- **Locked-out user?** There is no email reset yet. `scripts/reset_password.py` prints a temporary password and signs
  the user out everywhere (instructions are in the script).

## Before you share a public instance

An instance anyone can reach lets anyone sign up and spend your Gemini quota.

- Set `ALLOW_REGISTRATION=false` for a private instance, or keep it on and watch your API budget.
- AI endpoints are rate limited per user (30 per minute, 100 per day by default) and sign-in per IP; tune them in
  [`config.py`](../src/spotonfit/config.py).
- Use a Gemini key from a **paid** (billing-enabled) Google Cloud project if people will upload real meal photos, so
  the content is not used to improve Google's products.
- Set `PRIVACY_CONTACT` so the privacy page (`/privacy`) tells people who to contact.
- Health data is sensitive. Run it only if you are prepared to look after other people's data.
