# P Platform — Non-security Cleanup & Bugfix Tracking (2026-07)

Functional errors, fragile code, and cruft noted during the 2026-07 security
review of the `P` app but out of scope for that review. Security findings are
tracked separately in `202607_security_work.md`.

## Status legend

- [ ] TODO — not started
- [~] IN PROGRESS
- [x] DONE
- [-] WON'T FIX / ACCEPTED (with reason)

---

## Bugs / logic errors

### A. Backwards temp-file cleanup in `edge_recording_get` — BUG
- [x] Invert the cleanup condition in `P/views.py`

**Where:** `P/views.py:512-514`.

```python
if run_executable(['ffmpeg', ...]):
    os.remove(full_name)
```

`run_executable()` (`utilities/files/fileops.py:492`) returns `True` on
**failure** and `False` on **success**. So the source `.mkv` (`full_name`) is
removed only when ffmpeg *fails*, and left on disk when ffmpeg *succeeds*.
Result: on success the source file leaks, and neither the cached `.mp4` nor the
stray `.mkv` in `TEMP_ROOT` is ever cleaned up — temp files accumulate.

**Fix approach (agreed):** invert the logic **here in `P/views.py`** so the
source is removed on success. **Do NOT** change `run_executable()` itself —
its `True==error` return contract is used elsewhere in the codebase, so
reworking the utility must be planned separately to avoid breaking other
callers. Keep this fix local to `P`.

> Follow-up (separate, not part of this fix): the cached `.mp4` and any stray
> `.mkv` are never purged from `TEMP_ROOT`. Consider a cleanup/retention step,
> but that is out of scope for the logic-inversion fix above.

### B. `error` is always `None` in the TokenError message — BUG
- [x] Fix the message in the `TokenError` handler (old debug line kept as a
      comment, may be needed again short-term)

**Where:** `P/views.py:428` (handler), variable init at `P/views.py:415`.

`error` is initialized to `None` and only assigned inside the
`except Exception` branch, which runs *after* the `TokenError` handler. So
`return consent_page(service, msg = f'Error: {e}, {error}')` always renders
`, None`. There is also a commented-out "proper" message directly above it.
Looks like leftover debugging — restore a sensible user-facing message (e.g.
the commented-out "Consent has expired. Please request new consent.").

### C. Duplicate URL registration for `p-service-rm` — BUG (dead route)
- [x] Remove the duplicate `path(...)` entry

**Where:** `P/urls.py:21` and `P/urls.py:40`.

`path('service/<uuid:service_id>/rm/', views.service_rm, name='p-service-rm')`
is registered twice with the same pattern and name. The second (line 40, under
the "Combined" section) is redundant. Remove one.

---

## Fragile code (unhandled `KeyError` paths)

### D. `extra_data['axis:organization']` accessed with `[]`
- [x] Guard the lookup / fail gracefully (`.get()` + explicit `ValueError` in
      `_get_service_and_connection`; `service_page` context now handles a
      missing/`None` org_arn instead of raising)

**Where:** `P/views.py:103` (`_get_service_and_connection`) and
`P/views.py:437` (`service_page` context).

Raises `KeyError` if the IdP did not return that claim, even though the token
is stored with `.get('userinfo', {})`. Handle the missing-claim case (or
validate at token-storage time).

### E. `token_data['userinfo']` accessed with `[]`
- [x] Use `.get(...)` consistently

**Where:** `P/views.py:368`.

The same value is stored two lines earlier via `.get('userinfo', {})`
(`P/views.py:354`), so the `[]` access here is inconsistent and `KeyError`s if
absent. (Note: this line is also flagged in the security doc, finding #5, for
leaking PII — the whole `debug_data` entry is likely to be removed there, which
would also resolve this.)

### F. `r.headers['Content-Type']` accessed with `[]`
- [x] Use `.get('Content-Type', '')`

**Where:** `P/serviceclient.py:731` (`VapixClient._response`).

`KeyError` if a response omits the `Content-Type` header.

---

## Cleanliness / cruft

### G. Duplicated list-view code (self-acknowledged)
- [x] Factor shared logic out of the two list views (extracted
      `ServiceSearchListJsonMixin`)

**Where:** `Services_ListJson` (`P/views.py:196`) and `MyServices_ListJson`
(`P/views.py:567`).

Identical `get_form` / `get_filters_from_form`. The code itself notes it:
`"the AI wasn't clever enough to share code / TODO: Share code"`
(`P/views.py:568`). Extract a shared base or mixin.

### H. Stray editor backup / swap files in the app tree
- [x] Remove artifacts and confirm they are gitignored (P's own `.gitignore`
      already covers `*~` and `*.swp`; files deleted)

**Where:** `P/` directory.

`views.py~`, `models.py~`, `admin.py~`, `.pre-commit-config.yaml.swp`,
`.work_log.txt.swp`. Editor artifacts that should not be in the tree; the `~`
backups contain older copies of the same source. Delete and ensure the ignore
rules cover `*~` and `*.swp`.
