# Workflow Reference

## Contents

1. Pairing sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Pairing Sequence

1. Confirm the active browser session, target collaborator, approved environment, and maximum allowed access before issuing anything.
2. Issue a **scoped, time-limited pairing credential** — for example a one-time CDP/session handle, a scoped WebSocket token, or a single-use access token bound to the specific session ID. Deliver it **out-of-band** (not in shared chat, logs, or screenshots) via a direct secure channel only. This prevents leakage through conversation history, screen recordings, or log aggregation.
3. Hand out scoped session credentials only after the bootstrap target and browser surface are confirmed.
4. Verify the collaborator's landing state and record revocation instructions alongside the pairing result.
5. Revoke the pairing credential on handoff completion or expiry; do not leave open tokens after the collaboration window closes.

## Decision Rules

- Pair to a known live session, not to a guessed hostname or remembered browser state.
- Prefer the narrowest possible scope for both bootstrap and ongoing access.
- Deliver credentials out-of-band only — never in shared chat, logs, or screenshots.
- Revoke pairing credentials as soon as the handoff is complete or the expiry window passes.
- Treat leaked or wrong-recipient credential events as immediate revocation triggers, not operational noise.
- Treat wrong-environment and connectivity-failure events as hard blockers requiring human confirmation before retry.

## Acceptance Checklist

- Target collaborator and browser session are explicit.
- Pairing credential is scoped to the specific session, time-limited, and delivered out-of-band.
- Bootstrap and ongoing access scopes are both recorded.
- Landing state is verified after pairing.
- Expiry and revocation path are present.
- Credential was revoked or confirmed expired at handoff close.
- Any unsafe broadening attempt is surfaced explicitly.

## Contract Notes

- Setup keys (one-time): Use short-lived one-time pairing keys for remote session bootstrap before issuing longer-lived tokens.
- Session tokens: Use scoped time-bounded session credentials for remote browser or host interactions.
- Credential delivery (out-of-band): Never share raw tokens in chat, logs, or screenshots; use a direct secure channel.
- Revocation on completion: Revoke pairing credentials at handoff close or expiry.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `browser-automation/open-browser` owns creating the visible session to be paired, via its Browser Acquisition ladder (reuse an installed browser before installing the Playwright browser).
- `browser-automation/setup-browser-cookies` owns authenticated state when the paired session must start on a protected surface.
