// dev-api.js — LOCAL DEV BACKEND ONLY (Vite plugin, in-memory, resets on restart).
// Implements the endpoints the frontend expects so everything runs with
// `npm run dev`. Replace with your real FastAPI service for production.
import crypto from 'node:crypto';
import {
  generateRegistrationOptions,
  verifyRegistrationResponse,
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} from '@simplewebauthn/server';
import { POSTS as SEED_POSTS } from './src/lib/mockPosts.js';

const RP_NAME = 'Veritas Wall (dev)';
const RP_ID = 'localhost';
const PEPPER = crypto.randomBytes(32); // System_Pepper (dev: regenerated each start)

const credentials = new Map(); // credId(base64url) -> { publicKey, counter, blindUid }
const challenges = new Map();  // cookie "cid" -> challenge
const sessions = new Map();    // cookie "sid" -> { blindUid, dci }
const posts = structuredClone(SEED_POSTS);
const votes = new Map();       // postId -> Map(blindUid -> { responses, dci })

// Blind_UID = HMAC-SHA256(public_key, pepper), shortened for display
const blindUidFor = (pubKey) => {
  const h = crypto.createHmac('sha256', PEPPER).update(pubKey).digest('hex');
  return `${h.slice(0, 4)}-${h.slice(4, 8)}`;
};

const parseCookies = (req) =>
  Object.fromEntries((req.headers.cookie || '').split(';').filter(Boolean).map((c) => {
    const i = c.indexOf('=');
    return [c.slice(0, i).trim(), decodeURIComponent(c.slice(i + 1))];
  }));

const readJson = (req) =>
  new Promise((resolve) => {
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => { try { resolve(JSON.parse(data || '{}')); } catch { resolve({}); } });
  });

const send = (res, code, obj, cookies = []) => {
  res.statusCode = code;
  res.setHeader('Content-Type', 'application/json');
  if (cookies.length) res.setHeader('Set-Cookie', cookies);
  res.end(JSON.stringify(obj));
};

const cookie = (k, v) => `${k}=${encodeURIComponent(v)}; HttpOnly; Path=/; SameSite=Lax`;
const clearCookie = (k) => `${k}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0`;

// Very rough stand-in for the de-anonymization NLP guard.
const guard = (text) => {
  if (/\b[A-Z]{2,4}\s?-?\d{3,4}\b/.test(text)) return 'Post may contain identifying details: a course code.';
  if (/\b(Prof(essor)?|Dr)\.?\s+[A-Z][a-z]+/.test(text)) return 'Post may contain identifying details: a named individual.';
  return null;
};

// DCI-weighted average per criterion (not a 1:1 count).
const aggregate = (post) => {
  const all = [...(votes.get(post.id)?.values() ?? [])];
  const out = {};
  for (const c of post.poll.criteria) {
    const wsum = all.reduce((s, v) => s + v.dci, 0);
    out[c.key] = wsum ? Math.round(all.reduce((s, v) => s + v.responses[c.key] * v.dci, 0) / wsum) : c.value;
  }
  return { aggregate: out, voters: all.length };
};

const startSession = (res, blindUid, dci = 1.0) => {
  const sid = crypto.randomUUID();
  sessions.set(sid, { blindUid, dci });
  return send(res, 200, { verified: true, blindUid, dci }, [cookie('sid', sid)]);
};

async function handler(req, res, next) {
      {
        if (!req.url?.startsWith('/api/')) return next();
        const path = req.url.split('?')[0];
        const cookies = parseCookies(req);
        const sess = sessions.get(cookies.sid);
        const hostOk = /^localhost(:\d+)?$/.test(req.headers.host || '');
        const ORIGIN = `http://${req.headers.host}`;
        if (path.startsWith('/api/webauthn/') && !hostOk) {
          return send(res, 400, { error: 'Open the app at http://localhost:PORT — passkeys do not work on other hostnames or IPs.' });
        }

        // ---- reads ----
        if (req.method === 'GET') {
          if (path === '/api/session') return send(res, 200, sess ?? { blindUid: null, dci: null }); // 200 either way: no console noise when logged out
          if (path === '/api/posts') return send(res, 200, posts);
          return next();
        }
        if (req.method !== 'POST') return next();

        const body = await readJson(req);
        try {
          // ---- registration ----
          if (path === '/api/webauthn/register/options') {
            const options = await generateRegistrationOptions({
              rpName: RP_NAME,
              rpID: RP_ID,
              userName: 'anonymous',
              userID: new Uint8Array(crypto.randomBytes(16)),
              attestationType: 'none',
              authenticatorSelection: { residentKey: 'required', userVerification: 'preferred' },
            });
            const cid = crypto.randomUUID();
            challenges.set(cid, options.challenge);
            return send(res, 200, options, [cookie('cid', cid)]);
          }
          if (path === '/api/webauthn/register/verify') {
            const expectedChallenge = challenges.get(cookies.cid);
            if (!expectedChallenge) return send(res, 400, { verified: false });
            const v = await verifyRegistrationResponse({
              response: body.credential, expectedChallenge,
              expectedOrigin: ORIGIN, expectedRPID: RP_ID,
            });
            if (!v.verified || !v.registrationInfo) return send(res, 400, { verified: false });
            const { credentialID, credentialPublicKey, counter } = v.registrationInfo;
            // v10 returns credentialID as a base64url string already (older versions: Uint8Array).
            const id = typeof credentialID === 'string' ? credentialID : Buffer.from(credentialID).toString('base64url');
            const blindUid = blindUidFor(Buffer.from(credentialPublicKey));
            credentials.set(id, { publicKey: credentialPublicKey, counter, blindUid });
            challenges.delete(cookies.cid);
            return startSession(res, blindUid);
          }

          // ---- sign in ----
          if (path === '/api/webauthn/authenticate/options') {
            const options = await generateAuthenticationOptions({ rpID: RP_ID, userVerification: 'preferred' });
            const cid = crypto.randomUUID();
            challenges.set(cid, options.challenge);
            return send(res, 200, options, [cookie('cid', cid)]);
          }
          if (path === '/api/webauthn/authenticate/verify') {
            const expectedChallenge = challenges.get(cookies.cid);
            const cred = credentials.get(body.credential?.id);
            if (!expectedChallenge || !cred) return send(res, 400, { verified: false });
            const v = await verifyAuthenticationResponse({
              response: body.credential, expectedChallenge,
              expectedOrigin: ORIGIN, expectedRPID: RP_ID,
              authenticator: {
                credentialID: body.credential.id, // base64url string (v10 API)
                credentialPublicKey: cred.publicKey,
                counter: cred.counter,
              },
            });
            if (!v.verified) return send(res, 400, { verified: false });
            cred.counter = v.authenticationInfo.newCounter;
            challenges.delete(cookies.cid);
            return startSession(res, cred.blindUid);
          }

          // ---- sign out ----
          if (path === '/api/logout') {
            sessions.delete(cookies.sid);
            return send(res, 200, { ok: true }, [clearCookie('sid')]);
          }

          // ---- gated endpoints ----
          if (path === '/api/posts') {
            if (!sess) return send(res, 401, { error: 'unauthenticated' });
            const text = String(body.body || '').trim();
            if (text.length < 40) return send(res, 422, { reason: 'Please write a little more — at least a couple of sentences.' });
            const reason = guard(text);
            if (reason) return send(res, 422, { reason });
            const paras = text.split(/\n+/).filter(Boolean);
            const firstSentence = (paras[0].match(/^.{10,120}?[.!?](\s|$)/) || [paras[0].slice(0, 90)])[0].trim();
            const post = {
              id: 'u' + Date.now(), dept: body.dept, dci: sess.dci, blindUid: sess.blindUid,
              title: firstSentence, excerpt: text.slice(0, 180) + (text.length > 180 ? '…' : ''),
              // Title is the first sentence; don't repeat it at the top of the body.
              body: (() => {
                const rest = paras[0].slice(firstSentence.length).trim();
                const out = rest ? [rest, ...paras.slice(1)] : paras.slice(1);
                return out.length ? out : paras;
              })(),
              timeBucket: 'Just now', lessons: 0,
              poll: { title: 'Does this point to a structural problem?', criteria: [
                { key: 'impact', label: 'Impact on students', value: 50 },
                { key: 'urgency', label: 'Urgency of a fix', value: 50 },
              ] },
            };
            posts.unshift(post);
            return send(res, 200, post);
          }
          const m = path.match(/^\/api\/posts\/([^/]+)\/poll$/);
          if (m) {
            if (!sess) return send(res, 401, { error: 'unauthenticated' });
            const post = posts.find((p) => p.id === m[1]);
            if (!post) return send(res, 404, { error: 'not found' });
            const r = body.responses || {};
            const valid = post.poll.criteria.every((c) => Number.isFinite(r[c.key]) && r[c.key] >= 0 && r[c.key] <= 100);
            if (!valid) return send(res, 400, { error: 'invalid responses' });
            if (!votes.has(post.id)) votes.set(post.id, new Map());
            if (!votes.get(post.id).has(sess.blindUid)) post.lessons += 1; // first response from this Blind_UID
            votes.get(post.id).set(sess.blindUid, { responses: r, dci: sess.dci }); // one vote per Blind_UID (re-submit updates it)
            return send(res, 200, { ok: true, ...aggregate(post) });
          }
        } catch (err) {
          console.error('[dev-api]', err.message);
          return send(res, 400, { verified: false, error: err.message });
        }
        next();
      }
}

// Works for both `npm run dev` and `npm run preview` (the compiled build).
export default function devApi() {
  return {
    name: 'veritas-dev-api',
    configureServer(server) { server.middlewares.use(handler); },
    configurePreviewServer(server) { server.middlewares.use(handler); },
  };
}
