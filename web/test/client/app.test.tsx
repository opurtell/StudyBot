import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn } from "./helpers";

const config = { environment: "test", devSignIn: false };
const topics = { "GET /api/topics?view=icp_pacer": { view: "icp_pacer", topics: [] } };
const emptyProgress = {
  "GET /api/progress": {
    sections: [],
    totals: { answered: 0, accuracy: null, streakDays: 0, studiedToday: false },
    weakest: null,
    recent: [],
  },
};

describe("home", () => {
  it("shows the guest view to anonymous visitors", async () => {
    mockApi({ "GET /api/me": anonymous, ...topics });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: /studying as a guest/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in with google/i })).toHaveAttribute("href", "/sign-in");
    expect(screen.getByText(/study aid only\. not clinical guidance/i)).toBeInTheDocument();
  });

  it("shows remaining quota to signed-in users", async () => {
    mockApi({ "GET /api/me": signedIn, ...emptyProgress });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: /signed in as medic@example.com/i })).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": anonymous, ...topics });
    const { container } = renderAt("/");
    await screen.findByRole("heading", { name: /studying as a guest/i });
    await screen.findByText(/no topics are available/i);
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
      ...topics,
      ...emptyProgress,
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

describe("settings", () => {
  it("sends /account to settings and offers guests sign-in", async () => {
    mockApi({ "GET /api/me": anonymous, ...topics });
    renderAt("/account");
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText(/saved in this browser/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /sign in/i }).length).toBeGreaterThan(0);
  });

  it("deletes the account only after confirmation", async () => {
    let deleted = false;
    mockApi({
      "GET /api/me": () => ({ body: deleted ? anonymous : signedIn }),
      ...topics,
      ...emptyProgress,
      "DELETE /api/me": () => {
        deleted = true;
        return { body: { ok: true } };
      },
    });
    renderAt("/settings");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /delete account/i }));
    expect(deleted).toBe(false);
    await user.click(screen.getByRole("button", { name: /yes, delete my account/i }));
    expect(await screen.findByRole("heading", { name: /studying as a guest/i })).toBeInTheDocument();
    expect(deleted).toBe(true);
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": signedIn, ...topics });
    const { container } = renderAt("/settings");
    await screen.findByRole("heading", { name: "Account" });
    expect(await axeViolations(container)).toEqual([]);
  });
});
