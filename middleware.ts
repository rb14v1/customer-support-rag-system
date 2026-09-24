// Harbour SSO — standard OIDC middleware (deterministic template)
// Reads credentials from process.env — never hardcoded.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// ─── Configuration (from env — never secrets in source) ──────────────────────

const OIDC_ISSUER = process.env.OIDC_ISSUER;
const OIDC_CLIENT_ID = process.env.OIDC_CLIENT_ID;
const OIDC_CLIENT_SECRET = process.env.OIDC_CLIENT_SECRET;

if (!OIDC_ISSUER || !OIDC_CLIENT_ID || !OIDC_CLIENT_SECRET) {
  throw new Error(
    "Missing OIDC environment variables. Set OIDC_ISSUER, OIDC_CLIENT_ID, and OIDC_CLIENT_SECRET."
  );
}

// ─── Public paths that do NOT require authentication ────────────────────────

const PUBLIC_PATHS = ["/healthz", "/_next", "/favicon.ico"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

// ─── OIDC helper (stub — wire to your IdP client at runtime) ────────────────

function getAuthUrl(request: NextRequest): string {
  const params = new URLSearchParams({
    response_type: "code",
    client_id: OIDC_CLIENT_ID,
    scope: "openid profile email",
    redirect_uri: new URL("/api/auth/callback", request.url).toString(),
    state: crypto.randomUUID(),
  });
  return `${OIDC_ISSUER}/authorize?${params.toString()}`;
}

// ─── Middleware ─────────────────────────────────────────────────────────────

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths through
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Check for a valid session token (cookie / bearer)
  const sessionToken = request.cookies.get("session_token")?.value;

  if (!sessionToken) {
    // Redirect to IdP for authentication
    const authUrl = getAuthUrl(request);
    return NextResponse.redirect(authUrl);
  }

  // TODO: Validate session_token with the IdP / session store
  // For now, treat any present token as valid and proceed
  return NextResponse.next();
}

// Only run middleware on application routes, not static assets
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
};
