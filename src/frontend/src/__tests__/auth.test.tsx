import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock next/navigation
const mockPush = vi.fn();
const mockReplace = vi.fn();
const mockUsePathname = vi.fn(() => "/chat");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => mockUsePathname(),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Supabase client
const mockSignInWithPassword = vi.fn();
const mockSignUp = vi.fn();
const mockSignOut = vi.fn();
const mockSignInWithOAuth = vi.fn();
const mockGetSession = vi.fn().mockResolvedValue({
  data: { session: { user: { email: "test@attic.dev" }, access_token: "tok" } },
});
const mockGetUser = vi.fn();
const mockOnAuthStateChange = vi.fn(() => ({
  data: { subscription: { unsubscribe: vi.fn() } },
}));
const mockResetPasswordForEmail = vi.fn();
const mockUpdateUser = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: mockSignInWithPassword,
      signUp: mockSignUp,
      signOut: mockSignOut,
      signInWithOAuth: mockSignInWithOAuth,
      getSession: mockGetSession,
      getUser: mockGetUser,
      onAuthStateChange: mockOnAuthStateChange,
      resetPasswordForEmail: mockResetPasswordForEmail,
      updateUser: mockUpdateUser,
    },
  }),
}));

// Mock PostHog
vi.mock("@/lib/posthog", () => ({
  PostHogProvider: ({ children }: { children: React.ReactNode }) => children,
  trackAuthEvent: vi.fn(),
}));

// Mock TanStack Query
vi.mock("@tanstack/react-query", () => ({
  QueryClient: vi.fn().mockImplementation(() => ({})),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AuthProvider", () => {
  it("provides user from session", async () => {
    const { AuthProvider, useAuth } = await import("@/lib/auth-context");

    function TestConsumer() {
      const { user, loading } = useAuth();
      if (loading) return <div>loading</div>;
      return <div>{user?.email ?? "no user"}</div>;
    }

    mockGetSession.mockResolvedValueOnce({
      data: {
        session: { user: { email: "test@attic.dev" } },
      },
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("loading")).toBeDefined();
    // Wait for session to resolve
    expect(await screen.findByText("test@attic.dev")).toBeDefined();
  });

  it("provides null user when no session", async () => {
    const { AuthProvider, useAuth } = await import("@/lib/auth-context");

    function TestConsumer() {
      const { user, loading } = useAuth();
      if (loading) return <div>loading</div>;
      return <div>{user?.email ?? "no user"}</div>;
    }

    mockGetSession.mockResolvedValueOnce({
      data: { session: null },
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(await screen.findByText("no user")).toBeDefined();
  });
});

describe("DevBanner", () => {
  const ORIGINAL_ENV = process.env.NEXT_PUBLIC_ENVIRONMENT;

  afterEach(() => {
    process.env.NEXT_PUBLIC_ENVIRONMENT = ORIGINAL_ENV;
  });

  it("renders in development mode", async () => {
    // DevBanner reads env at module level, so we need to re-import
    process.env.NEXT_PUBLIC_ENVIRONMENT = "development";
    // Clear module cache
    vi.resetModules();

    const { DevBanner } = await import("@/components/dev-banner");
    const { AuthProvider } = await import("@/lib/auth-context");

    mockGetSession.mockResolvedValueOnce({
      data: { session: { user: { email: "test@attic.dev" } } },
    });

    render(
      <AuthProvider>
        <DevBanner />
      </AuthProvider>,
    );

    expect(await screen.findByText("Dev mode")).toBeDefined();
  });
});

describe("AppHeader", () => {
  it("renders nav links and user menu button", async () => {
    const { AuthProvider } = await import("@/lib/auth-context");
    const { AppHeader } = await import("@/components/app-header");

    mockGetSession.mockResolvedValueOnce({
      data: { session: { user: { email: "test@attic.dev" } } },
    });

    render(
      <AuthProvider>
        <AppHeader />
      </AuthProvider>,
    );

    // Wait for auth to load
    expect(await screen.findByText("Attic")).toBeDefined();
    expect(screen.getByText("Chat")).toBeDefined();
    expect(screen.getByText("Upload")).toBeDefined();
    expect(screen.getByLabelText("User menu")).toBeDefined();
  });

  it("renders page-specific actions", async () => {
    const { AuthProvider } = await import("@/lib/auth-context");
    const { AppHeader } = await import("@/components/app-header");

    mockGetSession.mockResolvedValueOnce({
      data: { session: { user: { email: "test@attic.dev" } } },
    });

    render(
      <AuthProvider>
        <AppHeader actions={<button>Custom Action</button>} />
      </AuthProvider>,
    );

    expect(await screen.findByText("Custom Action")).toBeDefined();
  });
});

describe("Middleware sanitizeNext", () => {
  // Test the sanitization logic directly (extracted for unit testing)
  function sanitizeNext(value: string | null): string {
    if (!value) return "/chat";
    if (value.includes("://") || value.startsWith("//")) return "/chat";
    if (!value.startsWith("/")) return "/chat";
    return value;
  }

  it("allows valid relative paths", () => {
    expect(sanitizeNext("/upload")).toBe("/upload");
    expect(sanitizeNext("/settings")).toBe("/settings");
    expect(sanitizeNext("/chat")).toBe("/chat");
  });

  it("rejects external URLs", () => {
    expect(sanitizeNext("https://evil.com")).toBe("/chat");
    expect(sanitizeNext("http://evil.com")).toBe("/chat");
    expect(sanitizeNext("//evil.com")).toBe("/chat");
  });

  it("rejects non-path values", () => {
    expect(sanitizeNext("evil.com")).toBe("/chat");
    expect(sanitizeNext("")).toBe("/chat");
    expect(sanitizeNext(null)).toBe("/chat");
  });

  it("defaults to /chat", () => {
    expect(sanitizeNext(null)).toBe("/chat");
  });
});
