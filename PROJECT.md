# Project: VB-Login Native Browser Process Execution Migration

## Architecture
- **Process Orchestration Layer**: `src/services/browser_service.py` manages native Chromium processes (`chrome.exe` / `msedge.exe`) using `subprocess.Popen`. It isolates profiles by `--user-data-dir="profiles/<channel_id>"`, maintains PID and process lifecycle, eliminates all automation flags and CDP connections, and monitors process exit via background threads.
- **Cookie Decryption & Extraction Engine**: `src/services/cookie_extractor.py` (or integrated within `src/services/`) safely snapshots Chromium's `Network/Cookies` SQLite database, extracts the 256-bit Master Key from `Local State` via Windows DPAPI (`CryptUnprotectData`), decrypts AES-256-GCM cookie blobs (stripping the modern Chromium 32-byte integrity header), converts 1601 timestamps to Unix epoch, and produces cookie structures directly ingestible by `SessionService` and `local_repo`.
- **Business Logic & Bridge Layer**: `src/services/account_service.py` and `src/web/api_bridge.py` interact with `BrowserService` without relying on Playwright. They manage channel sessions, bulk launches, and presence state for the pywebview Web UI.
- **Packaging & Dependency Layer**: PyInstaller spec files (`VB-Login.spec`, `VBLogin.spec`), `requirements.txt`, and build scripts (`build_exe.ps1`, GitHub Actions) stripped of `playwright` dependencies.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Windows Browser Detection | Detect Google Chrome via Registry/ProgramFiles/LocalAppData, fallback to Microsoft Edge | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Native Process Execution | Launch browser via `subprocess.Popen` with `--user-data-dir` and natural flags, zero automation flags | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Process Lifecycle & PID Tracking | Real PID tracking, `is_channel_open`, `close_channel_browser` via `taskkill /F /T`, `close_all_browsers` | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Profile Independence & Concurrency | Unique profile directories in `profiles/<channel_id>`, concurrent execution without `SingletonLock` | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Safe SQLite Snapshot & Lock Prevention | Copy `Network/Cookies` and journal/WAL files to temporary directory before read-only SQLite querying | M3 | ORIGINAL_REQUEST §R3 |
| 6 | DPAPI & AES-256-GCM Decryption | Extract Master Key from `Local State` via DPAPI, decrypt v10 cookies, strip 32-byte header, convert timestamps | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Vault & Session Integration | Transform extracted cookies to dictionary format compatible with `SessionCookie`, `prune_cookies`, and Vault storage | M3 | ORIGINAL_REQUEST §R3 |
| 8 | Dependency & Packaging Cleanup | Remove `playwright` from `requirements.txt`, PyInstaller spec files, build scripts; verify Web UI compatibility | M4 | ORIGINAL_REQUEST §R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Native Browser Launcher & Lifecycle | Browser detection, `subprocess.Popen` launcher, PID tracking, process termination, `_active_contexts` alias | none | PLANNED |
| M2 | Multi-Profile Concurrency & Isolation | Verification and hardening of multi-window execution, lock file collision avoidance, profile directory layout | M1 | PLANNED |
| M3 | Safe SQLite Cookie Extraction & Vault Integration | SQLite snapshot reader, DPAPI & AES-GCM decryption, 32-byte header handling, timestamp conversion, Vault sync | M1 | PLANNED |
| M4 | Dependencies & Packaging Cleanup | Remove playwright from requirements.txt, specs, build scripts, verify zero breaking changes in api_bridge / UI | M1, M3 | PLANNED |
| M5 | Final E2E Test Suite Pass & Adversarial Hardening | Pass 100% of E2E tests (Tiers 1-4), adversarial test hardening (Tier 5) | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### BrowserService ↔ AccountService
- `BrowserService.launch_channel_browser(channel_id: str, target_url: str = "https://accounts.google.com", cookies: Optional[List[Dict[str, Any]]] = None, on_started: Optional[Callable[[], None]] = None, on_closed: Optional[Callable[[List[Dict[str, Any]]], None]] = None, on_error: Optional[Callable[[Exception], None]] = None, on_autosave: Optional[Callable[[List[Dict[str, Any]]], None]] = None) -> None`: Launches browser in background thread, invokes `on_started` once running, monitors process, invokes `on_closed(extracted_cookies)` upon process termination.
- `BrowserService.is_channel_open(channel_id: str) -> bool`: Returns `True` if process for `channel_id` is currently alive.
- `BrowserService.close_channel_browser(channel_id: str) -> bool`: Forcefully terminates process tree for `channel_id` using Windows `taskkill /F /T /PID <pid>`.
- `BrowserService.close_all_browsers() -> int`: Terminates all active channel browser processes and returns count of terminated channels.
- `BrowserService._active_contexts`: Property returning dictionary of active channel IDs to process records for backward compatibility with `account_service.release_user_channels()`.

### SyncService (online liên máy qua Firebase RTDB REST, stdlib-only)
- Root RTDB: `vbsync/` (`presence/{mid}`, `locks/{ch}`, `requests/{rid}`, `inbox/{holderkey}/{rid}`, `health/{ch}`, `signals/{mid}/{ch}`).
- `SyncService.tick()` (10s, background): push presence + keepalive owned locks + pull locks/health/inbox + theo dõi outbox + nhận release-signal.
- Lock fresh < 45s; stale -> takeover; máy phân biệt bằng `data/.machine_id` (kể cả trùng tên/gmail).
- `AccountService.launch_channel` từ chối khi máy khác giữ fresh; `force_release_channel(..., remote_force)`; approve remote -> release-signal để máy giữ tự đóng browser (auto-yield).
- KHÔNG sync cookies (DPAPI gắn máy). Offline/token hết hạn -> local-only (fail-open).
### CookieExtractor ↔ BrowserService / Vault
- `CookieExtractor.extract_cookies_for_profile(profile_path: Path) -> List[Dict[str, Any]]`: Takes profile directory path, extracts Master Key from `Local State`, creates temporary snapshot of `Default/Network/Cookies`, queries SQLite, decrypts AES-256-GCM cookies, strips integrity header, converts `expires_utc` to Unix epoch, returns standard cookie dictionaries:
  - `name`: str
  - `value`: str
  - `domain`: str
  - `path`: str
  - `expires`: float (Unix timestamp)
  - `httpOnly`: bool
  - `secure`: bool
  - `sameSite`: str ("Lax", "Strict", "None")

## Code Layout
- `src/services/browser_service.py`: Native browser process management, detection, and lifecycle.
- `src/services/cookie_extractor.py`: Dedicated cookie extraction, DPAPI decryption, and SQLite snapshot reader.
- `src/services/account_service.py`: Business logic coordinating channels, accounts, and session storage.
- `src/web/api_bridge.py`: pywebview JavaScript bridge exposing application methods to Web UI.
- `requirements.txt`: Python package requirements (without playwright).
- `VB-Login.spec`, `VBLogin.spec`: PyInstaller build specifications.
- `tests/`: Opaque-box E2E test suite.
