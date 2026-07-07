# P Platform — Security Review & Work Tracking (2026-07)

Security review of the `P` app (Python code), focused on: tenant isolation
(reading/writing outside the tenant identified by the hostname), remote code
execution risk, and leaking of private data.

Scope reviewed: `P/views.py`, `P/urls.py`, `P/models.py`, `P/oauth.py`,
`P/utils.py`, `P/forms.py`, `P/serviceclient.py`, plus dependencies
`device_tool/device_tool.py`, `utilities/files/fileops.py`, tenant routing
(`tenants/settings.py`) and nginx config (`other_files/tenant.conf`).

## Status legend

- [ ] TODO — not started
- [~] IN PROGRESS
- [x] DONE
- [-] WON'T FIX / ACCEPTED (with reason)

## Overall assessment

Tenant isolation is fundamentally sound: the `Service` / `OAuthToken` /
`EndUser` / `ConsentRequest` models live in the per-tenant SQLite DB and every
ORM query is auto-scoped by `TenantRouter` via the request hostname.
`TEMP_ROOT` and the nginx `internal` download locations are rooted per-tenant.
No shell injection / direct RCE was found (the only `subprocess` call uses a
list argv, not a shell). The remaining issues concern over-privileged token
exposure, one cross-tenant file-write path via a device-controlled filename,
a cache key that can bypass an access decision, and missing rate limiting on
public/abusable endpoints.

---

## Findings

### 1. Admin-scoped OAuth access token handed to the browser — MEDIUM
- [-] Narrow the OAuth scope — **BLOCKED / ACCEPTED for now**

**Where:** `P/views.py:451` (`service_token`), scope at `P/oauth.py:59`.

`service_token` returns the raw bearer token as the HTTP body to any user with
`P.view_service`, for any `service_id`:

```python
authenticator = P_OAuth2Authenticator(service.oauth_token)
return HttpResponse(content = authenticator.token(), status = 200)
```

`authenticator.token()` → `OAuthToken.get_token()` returns the **access
token** (`P/models.py:151,183`), not the refresh token. The refresh token
stays server-side, so the exposed credential is time-limited (bounded by
`expires_at`), not indefinitely refreshable by the holder.

**Residual risk:** the consented scope is hardcoded to
`openid offline administrator` (`P/oauth.py:59`), so within the token's
lifetime a leaked access token grants full administrator control of the end
user's Axis organization. It is exposed to client-side JS for any service to
any `P.view_service` holder.

**Intended fix:** request the narrowest scope the browser-side flow actually
needs instead of `administrator`. **Current blocker:** the IdP presently
requires the `administrator` scope, so this cannot be narrowed at this time.
Re-evaluate when/if the IdP supports a narrower scope. Handing a *correctly
scoped* bearer token to the browser is an acceptable pattern; the scope is the
problem, not the mechanism.

> Note: the valid narrower scope string is a question for the Axis
> OAuth/consent documentation — it is not derivable from this codebase. Do not
> assume role names from `serviceclient.py` (`STREAM_VIDEO`, `DEVICE_MANAGEMENT`,
> etc.) are OAuth scopes; those are GraphQL access *roles*, a different concept.

### 2. Cross-tenant file write via device-controlled download filename — MEDIUM/HIGH
- [ ] Sanitize the download filename in `_file_download`

**Where:** `device_tool/device_tool.py:875-879`, reached from
`P/views.py:511` (`edge_recording_get` → `ExportRecording`).

The output path is built from the camera's `Content-Disposition` filename,
unsanitized:

```python
if not (name := req.headers.get_filename()):
    name = os.path.basename(urlparse(url).path) or "downloaded_file"
with open(full_name := f'{folder}/{name}', 'wb') as f:
```

A malicious/compromised camera (or a MITM of the edgelink response) can return
`filename="../<other-tenant>/private_data/…"` and write/clobber files
**outside this tenant's `TEMP_ROOT`**, defeating the otherwise-clean tenant
file isolation. This is the single biggest hole against the "no writing
outside the tenant" requirement.

**Suggested fix:** apply `os.path.basename(name)` and reject `..` / absolute
paths before joining to `folder`.

### 3. Recording export cache keyed only on `rec_id` — MEDIUM (authz smell)
- [ ] Include `service_id` + `device_id` in the cache key

**Where:** `P/views.py:509`.

```python
if not os.path.isfile(mp4_name := f'{tenant.TEMP_ROOT}/{rec_id}.mp4'):
```

The cache filename ignores `service_id` and `device_id`. Within a tenant, a
request for `service A / device X / rec_id=N` returns a previously-exported
file for a different service/device if their recording IDs collide — the
device is never contacted to re-authorize. Contained to one tenant (not a
cross-tenant leak) and Axis rec-ids are fairly unique, but an access decision
should not be bypassable by a cache hit.

**Suggested fix:** key the cache on `service_id` + `device_id` + `rec_id`
(or a hash of them).

### 4. Unencoded params injected into the device VAPIX query string — LOW
- [ ] URL-encode `disk_id`, `rec_id`, `device_id` before building the request

**Where:** `device_tool/device_tool.py:1664` (`ExportRecording`), device URL
build in `serviceclient.py`.

`disk_id` and `rec_id` (URL `<str>` segments, so they may contain `&`, `=`,
`?`) are interpolated raw into the `exportrecording.cgi` query, and
`device_id` into the edgelink URL path. `<str>` blocks `/`, so no path
traversal, and the target is always the end user's own camera (already fully
accessible to the service), so impact is low.

**Suggested fix:** URL-encode these values as defense-in-depth against
parameter smuggling.

### 5. `userinfo` echoed into the consent-success page — LOW
- [ ] Remove `debug_data` from the rendered context

**Where:** `P/views.py:368`.

```python
context.update({'service': service, 'debug_data': token_data['userinfo']})
```

Looks like leftover debugging; it exposes IdP profile claims (PII) in a
rendered page. Remove before production.

### 6. Broad "view all services" authorization — BY DESIGN, confirm intended
- [ ] Confirm this is acceptable for production (decision, not code change)

**Where:** `P/views.py:410-411` (the per-employee scoping is commented out).

Any `P.view_service` holder can open any service, list its devices, pull
tokens, and download recordings for every end user in the tenant. The model
docstring (`P/models.py`) says this is intentional for the demonstrator.
Flagged so it is a conscious decision: in production one compromised/curious
employee account = access to all end users' cameras. (End-user-facing views
`MyServiceEdit` / `service_rm` / `service_revoke` are properly object-scoped
via `is_authorized` / `can_delete` / `can_revoke` — those are fine.)

---

## nginx-level protection (rate limiting)

These endpoints have no throttling and would benefit from `limit_req` zones.

- [ ] **`send_consent_email`** (`P/views.py:460`) — each call sends an email
  (and BCCs the org). No per-user/per-service cooldown → email-bombing / cost
  abuse. Rate-limit this path; ideally also add a server-side resend cooldown
  on `ConsentRequest.requested_at`.
- [ ] **`oauth_callback` / `oauth_start`** (`consent/<uuid>/`,
  `oauth/callback/`) — public. UUID gating makes brute force impractical, but
  throttle to blunt automated probing.
- [ ] **`service_token`, `service_list_devices`, `edge_recording_list/get`** —
  each call fans out to the Axis GraphQL/edgelink API and can trigger a device
  export + ffmpeg transcode. Rate-limit to prevent a logged-in user from
  hammering the upstream API or spawning many concurrent ffmpeg processes
  (a cheap local DoS).
- [ ] **`LandingPage`** (`/`) — public; standard connection-level limiting.

---

## To investigate

- [ ] **`P/oauth.py:58` — scope sourcing.** The line above the hardcoded scope
  is commented out:
  ```python
  #          'scope': ' '.join(social_app.settings.get('scope'))
             'scope': 'openid offline administrator'
  ```
  This suggests the scope was at one point meant to come from the SocialApp
  config rather than being hardcoded. Investigate whether scope should be
  driven from `social_app.settings` (a single, admin-controlled source) instead
  of the hardcoded string. This does not by itself fix finding #1 (the IdP
  still requires `administrator` today), but it is the cleaner place to control
  scope once a narrower one becomes available.

---

## Confirmed OK (no action)

- No shell / `eval` / `os.system`; the only subprocess (`run_executable`,
  ffmpeg) uses list argv — no command injection.
- Tenant DB routing correctly isolates all `P` records by hostname; a
  `service_id` UUID from one tenant cannot resolve in another's DB.
- OAuth `state` is validated by authlib in the callback; the email consent link
  uses an unguessable UUID and checks `requested_at`.
- Token refresh is correctly serialized with a per-token Redis lock
  (`P/models.py:153`).
- End-user self-management views are object-scoped (`MyServiceEdit.is_authorized`,
  `Service.can_delete` / `can_revoke`).
