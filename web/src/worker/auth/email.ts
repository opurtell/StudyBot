import type { Logger } from "../lib/log";

export interface OutgoingEmail {
  to: string;
  subject: string;
  text: string;
  html: string;
}

export const devOutbox: OutgoingEmail[] = [];

export function buildMagicLinkEmail(to: string, link: string, ttlMinutes: number): OutgoingEmail {
  const subject = "Your sign-in link for Clinical Recall Assistant";
  const text = [
    "Use this link to sign in to Clinical Recall Assistant:",
    "",
    link,
    "",
    `The link works once and expires in ${ttlMinutes} minutes.`,
    "If you didn't ask to sign in, you can ignore this email.",
  ].join("\n");
  const html = `<!doctype html><html><body style="font-family:Georgia,serif;color:#1b1c18;background:#fbf9f3;padding:24px">
<p>Use this link to sign in to Clinical Recall Assistant:</p>
<p><a href="${link}" style="color:#2d5a54;font-weight:bold">Sign in</a></p>
<p style="font-size:13px;color:#404847">The link works once and expires in ${ttlMinutes} minutes. If you didn't ask to sign in, you can ignore this email.</p>
</body></html>`;
  return { to, subject, text, html };
}

export async function sendEmail(env: Env, log: Logger, message: OutgoingEmail): Promise<void> {
  if (!env.EMAIL) {
    if (env.ENVIRONMENT === "staging" || env.ENVIRONMENT === "production") {
      throw new Error("EMAIL binding is not configured");
    }
    devOutbox.push(message);
    if (devOutbox.length > 50) devOutbox.shift();
    log.info("dev_email_captured", { subject: message.subject, devText: message.text });
    return;
  }
  await env.EMAIL.send({
    to: message.to,
    from: { email: env.EMAIL_FROM, name: env.EMAIL_FROM_NAME },
    subject: message.subject,
    text: message.text,
    html: message.html,
  });
}
