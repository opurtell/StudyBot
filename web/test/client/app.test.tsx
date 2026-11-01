import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn } from "./helpers";

const config = { environment: "test", devSignIn: false };

describe("home", () => {
  it("shows the guest view to anonymous visitors", async () => {
    mockApi({ "GET /api/me": anonymous });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: /studying as a guest/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in with google/i })).toHaveAttribute("href", "/sign-in");
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
  it("sends the user to Google", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
    renderAt("/sign-in");
    expect(await screen.findByRole("link", { name: /continue with google/i })).toHaveAttribute("href", "/api/auth/google/start");
    expect(screen.queryByRole("button", { name: /dev sign-in/i })).not.toBeInTheDocument();
  });

  it.each([
    ["cancelled", /cancelled/i],
    ["expired", /took too long/i],
    ["unverified_email", /isn't verified/i],
    ["something-new", /didn't work/i],
  ])("explains the %s error from the callback", async (code, message) => {
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
    renderAt(`/sign-in?error=${code}`);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("offers dev sign-in only when the server allows it", async () => {
    let signedInNow = false;
    mockApi({
      "GET /api/me": () => ({ body: signedInNow ? signedIn : anonymous }),
      "GET /api/config": { environment: "development", devSignIn: true },
      "POST /api/auth/dev-sign-in": () => {
        signedInNow = true;
        return { body: { ok: true } };
      },
    });
    renderAt("/sign-in");
    await userEvent.setup().click(await screen.findByRole("button", { name: /dev sign-in/i }));
    expect(await screen.findByRole("heading", { name: /signed in as medic@example.com/i })).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
    const { container } = renderAt("/sign-in?error=cancelled");
    await screen.findByRole("alert");
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("account", () => {
  it("sends anonymous visitors to sign-in", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/config": config });
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
