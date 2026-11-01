import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn, stubTurnstile } from "./helpers";

const config = { turnstileSiteKey: "1x00000000000000000000AA", environment: "test" };

describe("home", () => {
  it("shows the guest view to anonymous visitors", async () => {
    mockApi({ "GET /api/me": anonymous });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: /studying as a guest/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in with email/i })).toHaveAttribute("href", "/sign-in");
    expect(screen.getByText(/study aid only\. not clinical guidance/i)).toBeInTheDocument();
  });

  it("shows remaining quota to signed-in users", async () => {
    mockApi({ "GET /api/me": signedIn });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: /signed in as medic@example.com/i })).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account" })).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": anonymous });
    const { container } = renderAt("/");
    await screen.findByRole("heading", { name: /studying as a guest/i });
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("sign-in", () => {
  it("sends the email and Turnstile token, then asks the user to check their email", async () => {
    stubTurnstile("ts-token");
    let sent: unknown;
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/config": config,
      "POST /api/auth/magic-link": (init: RequestInit | undefined) => {
        sent = JSON.parse(String(init?.body));
        return { status: 202, body: { ok: true } };
      },
    });
    renderAt("/sign-in");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "medic@example.com");
    await waitFor(() => expect(screen.getByTestId("turnstile")).toBeInTheDocument());
    await new Promise((r) => setTimeout(r, 5));
    await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }));
    expect(await screen.findByRole("heading", { name: /check your email/i })).toBeInTheDocument();
    expect(sent).toEqual({ email: "medic@example.com", turnstileToken: "ts-token" });
  });

  it("shows the server's error message", async () => {
    stubTurnstile();
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/config": config,
      "POST /api/auth/magic-link": { status: 429, body: { error: "rate_limited", message: "Too many sign-in requests. Wait a minute and try again." } },
    });
    renderAt("/sign-in");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "medic@example.com");
    await new Promise((r) => setTimeout(r, 5));
    await user.click(screen.getByRole("button", { name: /email me a sign-in link/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/too many sign-in requests/i);
  });

  it("has no detectable accessibility violations", async () => {
    stubTurnstile();
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
    const { container } = renderAt("/sign-in");
    await screen.findByLabelText("Email");
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("verify", () => {
  it("signs in only after the user confirms, and strips the token from the URL", async () => {
    window.history.replaceState(null, "", "/auth/verify#token=abc123");
    let verifyBody: unknown;
    let signedInNow = false;
    mockApi({
      "GET /api/me": () => ({ body: signedInNow ? signedIn : anonymous }),
      "POST /api/auth/verify": (init: RequestInit | undefined) => {
        verifyBody = JSON.parse(String(init?.body));
        signedInNow = true;
        return { body: { ok: true } };
      },
    });
    renderAt("/auth/verify");
    const button = await screen.findByRole("button", { name: "Sign in" });
    expect(verifyBody).toBeUndefined();
    expect(window.location.hash).toBe("");
    await userEvent.setup().click(button);
    expect(await screen.findByRole("heading", { name: /signed in as medic@example.com/i })).toBeInTheDocument();
    expect(verifyBody).toEqual({ token: "abc123" });
  });

  it("explains an expired link", async () => {
    window.history.replaceState(null, "", "/auth/verify#token=old");
    mockApi({
      "GET /api/me": anonymous,
      "POST /api/auth/verify": { status: 400, body: { error: "invalid_or_expired_link", message: "This sign-in link is invalid or has expired." } },
    });
    renderAt("/auth/verify");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid or has expired/i);
  });

  it("handles a missing token", async () => {
    mockApi({ "GET /api/me": anonymous });
    renderAt("/auth/verify");
    expect(await screen.findByRole("heading", { name: /link not recognised/i })).toBeInTheDocument();
  });
});

describe("account", () => {
  it("sends anonymous visitors to sign-in", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
    stubTurnstile();
    renderAt("/account");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("deletes the account only after confirmation", async () => {
    let deleted = false;
    mockApi({
      "GET /api/me": () => ({ body: deleted ? anonymous : signedIn }),
      "DELETE /api/me": () => {
        deleted = true;
        return { body: { ok: true } };
      },
    });
    renderAt("/account");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /delete account/i }));
    expect(deleted).toBe(false);
    await user.click(screen.getByRole("button", { name: /yes, delete my account/i }));
    expect(await screen.findByRole("heading", { name: /studying as a guest/i })).toBeInTheDocument();
    expect(deleted).toBe(true);
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": signedIn });
    const { container } = renderAt("/account");
    await screen.findByRole("heading", { name: "Account" });
    expect(await axeViolations(container)).toEqual([]);
  });
});
