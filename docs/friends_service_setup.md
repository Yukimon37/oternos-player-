# OTERNOS Friends Setup

OTERNOS Friends uses Discord only to sign people in. It never receives or
stores Discord passwords. It stores a display name, OTERNOS friend code,
friend requests, and optional listening activity.

## What Needs To Be Live

The desktop app connects to a small Cloudflare Worker with a D1 database. This
is a free online service for OTERNOS Friends, separate from the Discord bot.

The deployment files live on the `friends-service` branch:

- `cloudflare/worker.js`
- `cloudflare/wrangler.jsonc`

## Cloudflare Deployment

1. Create a free Cloudflare account.
2. Go to **Workers & Pages** and choose **Create application**.
3. Choose **Import a repository**, connect GitHub, then select
   `Yukimon37/oternos-player-` and the `friends-service` branch.
4. Set the project **Root Directory** to `cloudflare`, name the Worker
   `oternos-friends`, then deploy it.
5. Open **D1 SQL Database**, create a database named `oternos-friends`, then
   open the Worker **Bindings** tab. Add that database with the binding name
   `DB`.
6. In the Worker **Variables and Secrets** tab, add:

   ```text
   DISCORD_CLIENT_ID=your_discord_client_id
   DISCORD_CLIENT_SECRET=your_discord_client_secret
   OTERNOS_SOCIAL_PUBLIC_URL=https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev
   ```

7. Redeploy the Worker. Opening
   `https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev/health` should return JSON
   with `"status": "ok"` and `"discord_configured": true`.

The Worker creates its own D1 tables automatically on the first request.

## Discord Setup

1. Open the Discord Developer Portal and choose the existing OTERNOS Discord
   application.
2. In **OAuth2**, add this Redirect URL using the exact Worker address:

   ```text
   https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev/v1/auth/discord/callback
   ```

3. Copy the application's **Client ID** and create a **Client Secret**.
4. Keep the secret only in Cloudflare. Never add it to this repository or the
   desktop app.

## Connecting The Desktop App During Testing

Before the public Friends service address is built into a release, launch the
app with this Windows environment variable set:

```powershell
$env:OTERNOS_SOCIAL_SERVICE_URL = "https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev"
.\OPEN_OTERNOS.bat
```

Then open **Friends** in OTERNOS and press **Sign in with Discord**.

Once the service address is confirmed, set `DEFAULT_SOCIAL_SERVICE_URL` in
`oternos/core/social.py`, rebuild OTERNOS, and make a normal friend release.

## Privacy Rules

- People can only add each other with an OTERNOS friend code.
- Current track details are private by default.
- A user has to enable **Share what I am listening to with friends** before
  activity is visible.
- Presence becomes offline shortly after the desktop app stops checking in.
- The service uses HTTPS in production. Local `http://127.0.0.1` is allowed
  only for development.
