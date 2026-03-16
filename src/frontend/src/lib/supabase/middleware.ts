import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/** Routes that require authentication. */
const PROTECTED_PREFIXES = ["/chat", "/upload", "/settings"];

/** Sanitize a redirect target — only allow relative paths. */
function sanitizeNext(value: string | null): string {
  if (!value) return "/chat";
  if (value.includes("://") || value.startsWith("//")) return "/chat";
  if (!value.startsWith("/")) return "/chat";
  return value;
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // Refresh the auth token by calling getUser().
  // IMPORTANT: Do not remove this. It refreshes the session cookie.
  let user = null;
  try {
    const { data } = await supabase.auth.getUser();
    user = data.user;
  } catch {
    // If Supabase is unreachable, treat as unauthenticated
  }

  // Protect authenticated routes: redirect unauthenticated users to /login
  const pathname = request.nextUrl.pathname;
  const isProtected = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix),
  );

  if (!user && isProtected) {
    const url = request.nextUrl.clone();
    const next = sanitizeNext(pathname);
    url.pathname = "/login";
    if (next !== "/chat") {
      url.searchParams.set("next", next);
    }
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
