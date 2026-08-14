/**
 * OTERNOS Friends for Cloudflare Workers + D1.
 *
 * Bind a D1 database named DB in the Cloudflare dashboard and configure:
 * DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, OTERNOS_SOCIAL_PUBLIC_URL.
 */

const DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize";
const DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token";
const DISCORD_USER_URL = "https://discord.com/api/users/@me";
const LOGIN_TTL_SECONDS = 10 * 60;
const SESSION_TTL_SECONDS = 90 * 24 * 60 * 60;
const PRESENCE_TTL_SECONDS = 90;

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  avatar_url TEXT NOT NULL DEFAULT '',
  friend_code TEXT NOT NULL UNIQUE,
  activity_sharing INTEGER NOT NULL DEFAULT 0,
  presence_online INTEGER NOT NULL DEFAULT 0,
  track_title TEXT NOT NULL DEFAULT '',
  track_artist TEXT NOT NULL DEFAULT '',
  last_seen REAL NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
  request_id TEXT PRIMARY KEY,
  login_key_hash TEXT NOT NULL,
  device_id TEXT NOT NULL,
  state TEXT NOT NULL,
  user_id TEXT,
  session_token TEXT,
  expires_at REAL NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  expires_at REAL NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS friend_requests (
  request_id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  to_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  state TEXT NOT NULL,
  created_at REAL NOT NULL,
  responded_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_friend_requests_to_state
ON friend_requests(to_user_id, state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_friend_requests_from_state
ON friend_requests(from_user_id, state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user
ON sessions(user_id, expires_at);
`;

const schemaTasks = new WeakMap();
const encoder = new TextEncoder();

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function now() {
  return Date.now() / 1000;
}

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function page(title, message, status = 200) {
  return new Response(
    `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title>` +
      `<style>body{margin:0;background:#161616;color:#f2f2f2;font:16px system-ui,sans-serif;display:grid;min-height:100vh;place-items:center}.box{max-width:420px;padding:32px;border:1px solid #373737;border-radius:16px;background:#202020}h1{margin-top:0;font-size:24px}p{color:#cfcfcf;line-height:1.5}</style>` +
      `</head><body><main class="box"><h1>${title}</h1><p>${message}</p></main></body></html>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } },
  );
}

function randomToken(byteLength = 32) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  let text = "";
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function sha256(value) {
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function ensureSchema(env) {
  if (!env.DB) throw new HttpError(503, "Friends storage is not configured yet.");
  let task = schemaTasks.get(env.DB);
  if (!task) {
    task = env.DB.exec(SCHEMA);
    schemaTasks.set(env.DB, task);
  }
  await task;
}

async function first(database, query, ...values) {
  return database.prepare(query).bind(...values).first();
}

async function all(database, query, ...values) {
  const result = await database.prepare(query).bind(...values).all();
  return result.results || [];
}

async function cleanup(database) {
  const timestamp = now();
  await database.batch([
    database.prepare("DELETE FROM sessions WHERE expires_at < ?").bind(timestamp),
    database.prepare("DELETE FROM login_attempts WHERE expires_at < ?").bind(timestamp),
  ]);
}

function publicUrl(env) {
  return String(env.OTERNOS_SOCIAL_PUBLIC_URL || "").trim().replace(/\/$/, "");
}

function oauthConfig(env) {
  const clientId = String(env.DISCORD_CLIENT_ID || "").trim();
  const clientSecret = String(env.DISCORD_CLIENT_SECRET || "").trim();
  const baseUrl = publicUrl(env);
  if (!clientId || !clientSecret || !baseUrl) {
    throw new HttpError(503, "Friends sign-in is not configured. Add Discord OAuth and public URL variables.");
  }
  return { clientId, clientSecret, baseUrl, redirectUri: `${baseUrl}/v1/auth/discord/callback` };
}

function profile(row) {
  return {
    user_id: String(row.user_id),
    display_name: String(row.display_name),
    avatar_url: String(row.avatar_url || ""),
    friend_code: String(row.friend_code),
    activity_sharing: Boolean(row.activity_sharing),
  };
}

function friend(row, relationship, requestId = "") {
  const online = Boolean(row.presence_online) && now() - Number(row.last_seen || 0) <= PRESENCE_TTL_SECONDS;
  const title = online && row.activity_sharing ? String(row.track_title || "").trim() : "";
  const artist = online && row.activity_sharing ? String(row.track_artist || "").trim() : "";
  const nowPlaying = [title, artist].filter(Boolean).join(" - ");
  return {
    user_id: String(row.user_id),
    display_name: String(row.display_name),
    avatar_url: String(row.avatar_url || ""),
    friend_code: String(row.friend_code),
    relationship,
    request_id: String(requestId),
    presence: nowPlaying ? "LISTENING" : online ? "ONLINE" : "OFFLINE",
    now_playing: nowPlaying,
  };
}

function bearerToken(request) {
  const value = String(request.headers.get("Authorization") || "").trim();
  if (!value.toLowerCase().startsWith("bearer ")) {
    throw new HttpError(401, "Sign in with Discord first.");
  }
  const token = value.slice(7).trim();
  if (token.length < 24) throw new HttpError(401, "Your Friends session is invalid.");
  return token;
}

async function currentUser(request, env) {
  const token = bearerToken(request);
  await cleanup(env.DB);
  const user = await first(
    env.DB,
    `SELECT users.* FROM sessions
     JOIN users ON users.user_id = sessions.user_id
     WHERE sessions.token_hash = ? AND sessions.expires_at >= ?`,
    await sha256(token),
    now(),
  );
  if (!user) throw new HttpError(401, "Your Friends session expired. Sign in again.");
  return user;
}

async function requestJson(request) {
  try {
    const value = await request.json();
    if (value && typeof value === "object" && !Array.isArray(value)) return value;
  } catch {
    // Handled below with the same useful error.
  }
  throw new HttpError(400, "Friends received an invalid request.");
}

async function newFriendCode(database) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  for (let attempt = 0; attempt < 40; attempt += 1) {
    let suffix = "";
    const bytes = new Uint8Array(6);
    crypto.getRandomValues(bytes);
    for (const byte of bytes) suffix += alphabet[byte % alphabet.length];
    const code = `OTR-${suffix}`;
    if (!(await first(database, "SELECT 1 FROM users WHERE friend_code = ?", code))) return code;
  }
  throw new HttpError(500, "Could not generate an OTERNOS friend code.");
}

function avatarUrl(discordUser) {
  const userId = String(discordUser.id || "").trim();
  const avatar = String(discordUser.avatar || "").trim();
  return userId && avatar ? `https://cdn.discordapp.com/avatars/${userId}/${avatar}.png?size=128` : "";
}

async function discordJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new HttpError(502, "Could not reach Discord. Try signing in again.");
  }
  if (!response.ok) throw new HttpError(502, "Discord did not complete the sign-in request.");
  try {
    const value = await response.json();
    if (value && typeof value === "object" && !Array.isArray(value)) return value;
  } catch {
    // Use the same friendly sign-in failure below.
  }
  throw new HttpError(502, "Discord returned an invalid sign-in response.");
}

async function startAuth(request, env) {
  const body = await requestJson(request);
  const deviceId = String(body.device_id || "").trim();
  const loginKey = String(body.login_key || "").trim();
  if (deviceId.length < 8 || deviceId.length > 160 || loginKey.length < 24 || loginKey.length > 200) {
    throw new HttpError(400, "Friends received an incomplete sign-in request.");
  }
  const config = oauthConfig(env);
  const requestId = randomToken(32);
  const expiresAt = now() + LOGIN_TTL_SECONDS;
  await cleanup(env.DB);
  await env.DB
    .prepare(`INSERT INTO login_attempts(request_id, login_key_hash, device_id, state, expires_at, created_at)
              VALUES (?, ?, ?, 'PENDING', ?, ?)`)
    .bind(requestId, await sha256(loginKey), deviceId, expiresAt, now())
    .run();
  return json({
    request_id: requestId,
    authorize_url: `${config.baseUrl}/v1/auth/discord?${new URLSearchParams({ state: requestId })}`,
    expires_at: expiresAt,
    client_id: config.clientId,
  });
}

async function beginDiscordAuth(url, env) {
  const state = String(url.searchParams.get("state") || "");
  const config = oauthConfig(env);
  await cleanup(env.DB);
  const attempt = await first(
    env.DB,
    "SELECT request_id FROM login_attempts WHERE request_id = ? AND state = 'PENDING' AND expires_at >= ?",
    state,
    now(),
  );
  if (!attempt) throw new HttpError(400, "This OTERNOS sign-in link has expired. Return to the app and try again.");
  const query = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    response_type: "code",
    scope: "identify",
    state,
    prompt: "consent",
  });
  return Response.redirect(`${DISCORD_AUTHORIZE_URL}?${query}`, 302);
}

async function discordCallback(url, env) {
  const error = String(url.searchParams.get("error") || "");
  const code = String(url.searchParams.get("code") || "");
  const state = String(url.searchParams.get("state") || "");
  if (error) return page("OTERNOS sign-in cancelled", "Return to the OTERNOS app and try again.", 400);
  if (!code || !state) return page("OTERNOS sign-in failed", "Discord did not return the required sign-in details.", 400);

  let config;
  try {
    config = oauthConfig(env);
    await cleanup(env.DB);
    const attempt = await first(
      env.DB,
      "SELECT request_id FROM login_attempts WHERE request_id = ? AND state = 'PENDING' AND expires_at >= ?",
      state,
      now(),
    );
    if (!attempt) return page("OTERNOS sign-in expired", "Return to the OTERNOS app and start again.", 400);

    const token = await discordJson(DISCORD_TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: new URLSearchParams({
        client_id: config.clientId,
        client_secret: config.clientSecret,
        grant_type: "authorization_code",
        code,
        redirect_uri: config.redirectUri,
      }),
    });
    const accessToken = String(token.access_token || "").trim();
    if (!accessToken) return page("OTERNOS sign-in failed", "Discord did not return an access token.", 502);

    const discordUser = await discordJson(DISCORD_USER_URL, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const userId = String(discordUser.id || "").trim();
    const displayName = String(discordUser.global_name || discordUser.username || "").trim().slice(0, 80);
    if (!userId || !displayName) return page("OTERNOS sign-in failed", "Discord did not return a usable profile.", 502);

    const existing = await first(env.DB, "SELECT friend_code FROM users WHERE user_id = ?", userId);
    const friendCode = existing ? String(existing.friend_code) : await newFriendCode(env.DB);
    const sessionToken = randomToken(40);
    const timestamp = now();
    await env.DB.batch([
      env.DB
        .prepare(`INSERT INTO users(user_id, display_name, avatar_url, friend_code, last_seen, created_at)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name, avatar_url = excluded.avatar_url`)
        .bind(userId, displayName, avatarUrl(discordUser), friendCode, timestamp, timestamp),
      env.DB
        .prepare("INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)")
        .bind(await sha256(sessionToken), userId, timestamp + SESSION_TTL_SECONDS, timestamp),
      env.DB
        .prepare("UPDATE login_attempts SET state = 'COMPLETE', user_id = ?, session_token = ? WHERE request_id = ?")
        .bind(userId, sessionToken, state),
    ]);
  } catch (failure) {
    return page("OTERNOS sign-in failed", failure instanceof Error ? failure.message : "Try signing in again.", 502);
  }
  return page("OTERNOS is connected", "You can close this page and return to the OTERNOS app.");
}

async function authStatus(url, request, env) {
  const requestId = String(url.searchParams.get("request_id") || "");
  const loginKey = String(request.headers.get("X-OTERNOS-Login-Key") || "").trim();
  if (!requestId || !loginKey) throw new HttpError(400, "This sign-in request is incomplete.");
  await cleanup(env.DB);
  const attempt = await first(env.DB, "SELECT * FROM login_attempts WHERE request_id = ?", requestId);
  if (!attempt || String(attempt.login_key_hash) !== (await sha256(loginKey))) {
    throw new HttpError(404, "This sign-in request is no longer available.");
  }
  if (attempt.state === "PENDING") return json({ state: "PENDING" });
  if (attempt.state !== "COMPLETE" || !attempt.user_id || !attempt.session_token) {
    throw new HttpError(400, "Discord sign-in did not complete.");
  }
  const user = await first(env.DB, "SELECT * FROM users WHERE user_id = ?", attempt.user_id);
  const response = { state: "COMPLETE", session_token: String(attempt.session_token), profile: profile(user) };
  await env.DB.prepare("DELETE FROM login_attempts WHERE request_id = ?").bind(requestId).run();
  return json(response);
}

async function listFriends(request, env) {
  const user = await currentUser(request, env);
  const userId = String(user.user_id);
  const friends = await all(
    env.DB,
    `SELECT users.* FROM friend_requests
     JOIN users ON users.user_id = CASE WHEN friend_requests.from_user_id = ? THEN friend_requests.to_user_id ELSE friend_requests.from_user_id END
     WHERE friend_requests.state = 'ACCEPTED' AND (friend_requests.from_user_id = ? OR friend_requests.to_user_id = ?)
     ORDER BY lower(users.display_name)`,
    userId,
    userId,
    userId,
  );
  const incoming = await all(
    env.DB,
    `SELECT friend_requests.request_id, users.* FROM friend_requests
     JOIN users ON users.user_id = friend_requests.from_user_id
     WHERE friend_requests.to_user_id = ? AND friend_requests.state = 'PENDING'
     ORDER BY friend_requests.created_at DESC`,
    userId,
  );
  return json({
    profile: profile(user),
    friends: friends.map((row) => friend(row, "FRIEND")),
    incoming_requests: incoming.map((row) => friend(row, "INCOMING", row.request_id)),
  });
}

async function createFriendRequest(request, env) {
  const user = await currentUser(request, env);
  const body = await requestJson(request);
  const friendCode = String(body.friend_code || "").trim().toUpperCase();
  if (friendCode.length < 5 || friendCode.length > 32) throw new HttpError(400, "Enter a valid OTERNOS friend code.");
  const target = await first(env.DB, "SELECT * FROM users WHERE friend_code = ?", friendCode);
  if (!target) throw new HttpError(404, "No OTERNOS user has that friend code.");
  if (String(target.user_id) === String(user.user_id)) throw new HttpError(400, "You cannot add yourself.");
  const existing = await first(
    env.DB,
    `SELECT * FROM friend_requests
     WHERE (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)
     ORDER BY request_id DESC LIMIT 1`,
    String(user.user_id),
    String(target.user_id),
    String(target.user_id),
    String(user.user_id),
  );
  if (existing && existing.state === "ACCEPTED") throw new HttpError(400, "You are already friends.");
  if (existing && existing.state === "PENDING") {
    if (String(existing.to_user_id) === String(user.user_id)) {
      throw new HttpError(400, "This person already sent you a request. Accept it in Friends.");
    }
    throw new HttpError(400, "That friend request is already pending.");
  }
  await env.DB
    .prepare("INSERT INTO friend_requests(from_user_id, to_user_id, state, created_at) VALUES (?, ?, 'PENDING', ?)")
    .bind(String(user.user_id), String(target.user_id), now())
    .run();
  return json({ ok: true });
}

async function acceptFriendRequest(requestId, request, env) {
  const user = await currentUser(request, env);
  if (!/^\d+$/.test(requestId)) throw new HttpError(404, "That friend request is no longer pending.");
  const result = await env.DB
    .prepare(`UPDATE friend_requests SET state = 'ACCEPTED', responded_at = ?
              WHERE request_id = ? AND to_user_id = ? AND state = 'PENDING'`)
    .bind(now(), Number(requestId), String(user.user_id))
    .run();
  if (!result.meta.changes) throw new HttpError(404, "That friend request is no longer pending.");
  return json({ ok: true });
}

async function removeFriend(friendId, request, env) {
  const user = await currentUser(request, env);
  if (!friendId || friendId.length > 160) throw new HttpError(404, "That friend connection does not exist.");
  const userId = String(user.user_id);
  const result = await env.DB
    .prepare(`UPDATE friend_requests SET state = 'REMOVED', responded_at = ?
              WHERE state = 'ACCEPTED' AND ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))`)
    .bind(now(), userId, friendId, friendId, userId)
    .run();
  if (!result.meta.changes) throw new HttpError(404, "That friend connection does not exist.");
  return json({ ok: true });
}

async function updatePresence(request, env) {
  const user = await currentUser(request, env);
  const body = await requestJson(request);
  const shareActivity = Boolean(body.share_activity);
  const online = Boolean(body.online);
  const title = shareActivity ? String(body.track_title || "").trim().slice(0, 180) : "";
  const artist = shareActivity ? String(body.track_artist || "").trim().slice(0, 180) : "";
  await env.DB
    .prepare(`UPDATE users
              SET activity_sharing = ?, presence_online = ?, track_title = ?, track_artist = ?, last_seen = ?
              WHERE user_id = ?`)
    .bind(Number(shareActivity), Number(online), title, artist, now(), String(user.user_id))
    .run();
  const fresh = await first(env.DB, "SELECT * FROM users WHERE user_id = ?", user.user_id);
  return json({ profile: profile(fresh) });
}

async function route(request, env) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") return new Response(null, { status: 204 });
  await ensureSchema(env);

  if (request.method === "GET" && url.pathname === "/health") {
    return json({
      status: "ok",
      service: "oternos-friends",
      discord_configured: Boolean(env.DISCORD_CLIENT_ID && env.DISCORD_CLIENT_SECRET && publicUrl(env)),
    });
  }
  if (request.method === "POST" && url.pathname === "/v1/auth/start") return startAuth(request, env);
  if (request.method === "GET" && url.pathname === "/v1/auth/discord") return beginDiscordAuth(url, env);
  if (request.method === "GET" && url.pathname === "/v1/auth/discord/callback") return discordCallback(url, env);
  if (request.method === "GET" && url.pathname === "/v1/auth/status") return authStatus(url, request, env);
  if (request.method === "POST" && url.pathname === "/v1/auth/logout") {
    const token = bearerToken(request);
    await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(await sha256(token)).run();
    return json({ ok: true });
  }
  if (request.method === "GET" && url.pathname === "/v1/friends") return listFriends(request, env);
  if (request.method === "POST" && url.pathname === "/v1/friends/requests") return createFriendRequest(request, env);
  const accept = url.pathname.match(/^\/v1\/friends\/requests\/([^/]+)\/accept$/);
  if (request.method === "POST" && accept) return acceptFriendRequest(decodeURIComponent(accept[1]), request, env);
  const remove = url.pathname.match(/^\/v1\/friends\/([^/]+)$/);
  if (request.method === "DELETE" && remove) return removeFriend(decodeURIComponent(remove[1]), request, env);
  if (request.method === "PUT" && url.pathname === "/v1/presence") return updatePresence(request, env);
  throw new HttpError(404, "That Friends service address does not exist.");
}

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (failure) {
      if (failure instanceof HttpError) return json({ detail: failure.message }, failure.status);
      console.error("OTERNOS Friends error", failure);
      return json({ detail: "OTERNOS Friends hit an unexpected error. Try again." }, 500);
    }
  },
};
