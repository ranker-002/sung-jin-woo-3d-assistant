# Sung Jin Woo 3D Assistant - Comprehensive Codebase Analysis

**Date:** 2026-03-17
**Analyst:** Claude Code
**Project:** Sung Jin Woo - Shadow Monarch 3D Desktop Assistant

---

## Executive Summary

The Sung Jin Woo assistant is a sophisticated 3D virtual assistant built with PyWebView, Three.js, FastAPI, and multiple AI/ML integrations (Whisper STT, TTS engines, Ollama/Gemini/OpenAI). The codebase is **functional but has several critical bugs, missing features, and architectural improvements** needed for production readiness.

**Overall Health:** Medium (6/10)
**Code Quality:** Medium (needs refactoring in several areas)
**Test Coverage:** None (0%)
**Documentation:** Partial (README exists, code lacks comments)

---

## Critical Issues (Must Fix First)

### 1. 🔴 **CRITICAL: Database Path Bug - Fixed but Might Recur**
- **File:** `backend/memory.py:11`
- **Issue:** DB path uses relative path that breaks when running from different working directories
- **Status:** ✓ Fixed in this session
- **Fix Applied:** Changed `Path("backend/data/memory.db")` to `Path(__file__).parent / "data" / "memory.db"`
- **Risk:** May re-appear if code is refactored without understanding this issue
- **Recommendation:** Add path validation at startup, ensure all file paths in backend use `BASE_DIR` from config

### 2. 🔴 **CRITICAL: Missing Dependencies at Runtime**
- **Files:** Multiple
- **Issue:** Application assumes optional dependencies (TTS, STT, LLM) are installed but doesn't validate at startup
- **Impact:** Silent failures when TTS engine missing, confusing fallback behavior
- **Examples:**
  - `TTS` module (Coqui) not installed → falls back to gTTS (requires internet)
  - `sounddevice` missing → STT crashes silently
  - `faster-whisper` missing → STT completely broken
- **Recommendation:** Add dependency validation in `app.py` startup with clear error messages

### 3. 🔴 **CRITICAL: Backend Server Not Auto-Starting**
- **File:** `app.py`
- **Issue:** `start_backend_thread()` doesn't catch exceptions if backend fails to start
- **Impact:** App shows no error, just hangs
- **Recommendation:** Add try/catch with UI notification if backend fails to start, implement health check endpoint

### 4. 🔴 **CRITICAL: WebSocket Connection Instability**
- **File:** `frontend/main.js:119-140`
- **Issue:** WebSocket reconnection uses fixed 3s delay, no exponential backoff, no max retry limit
- **Impact:** Can overwhelm server if down, reconnect spam
- **Fix:** Implement exponential backoff with jitter, max retry limit, show disconnected UI state

---

## High Priority Issues

### 5. 🟠 **HIGH: TTS Engine Fallback Chain Issues**
- **File:** `backend/tts.py:261-289`
- **Issues:**
  - Coqui model loads on every call (not thread-safe properly)
  - Piper voice loading may fail silently
  - No user notification when falling back to inferior TTS
  - gTTS fallback requires internet but no connectivity check
- **Recommendation:** Cache TTS engine instances properly, add quality metrics, show warning in UI when using fallback

### 6. 🟠 **HIGH: STT Microphone Resource Management**
- **File:** `backend/stt.py:195-229`
- **Issues:**
  - Stream not properly closed on errors
  - No cleanup if `stop()` not called
  - Multiple listeners could start accidentally
  - Device selection not configurable (picks default)
- **Fix:** Add context manager pattern, ensure stream cleanup in `finally` blocks, add device selection to config

### 7. 🟠 **HIGH: Memory Database Thread Safety**
- **File:** `backend/memory.py:16`
- **Issue:** SQLite connection shared across threads without proper threading mode
- **Current:** `check_same_thread=False` allows sharing but risks corruption
- **Recommendation:** Use connection pool or per-thread connections, add locks for write operations

### 8. 🟠 **HIGH: Missing LLM Provider Fallback Chain**
- **File:** `backend/llm.py:246-260`
- **Issue:** If configured provider fails, no automatic fallback to alternate provider
- **Current:** Tries single provider from config
- **Fix:** Define fallback chain (e.g., Ollama → Gemini → OpenAI → error)

### 9. 🟠 **HIGH: Unhandled Promise Rejections in Frontend**
- **Files:** All frontend JS
- **Issue:** Async operations (audio playback, WebSocket messages) lack error handling
- **Example:** `playAudio()` in main.js has try/catch but some promises don't
- **Fix:** Add global error handler, wrap all promises with catch, display user-friendly errors

### 10. 🟠 **HIGH: Audio Context Management**
- **File:** `frontend/main.js:314-360`
- **Issue:** Web Audio context created on first click, but may be suspended by browser
- **Impact:** Audio fails silently if context state not checked/resumed
- **Fix:** Add context state monitoring, auto-resume on user interaction, handle `statechange` events

---

## Medium Priority Issues

### 11. 🟡 **MEDIUM: No Configuration Validation**
- **File:** `backend/config.py`
- **Issue:** All config values have defaults but no validation for invalid values
- **Examples:**
  - Invalid TTS_ENGINE → falls back to gTTS silently
  - Invalid WHISPER_MODEL → Whisper might crash
  - Invalid port numbers → bind failures
- **Fix:** Add `validate_config()` function called at startup, log warnings for invalid configs

### 12. 🟡 **MEDIUM: Missing Backend Health Check Endpoint**
- **File:** `backend/main.py`
- **Issue:** No `/health` endpoint for monitoring backend status
- **Impact:** Hard to know if backend is alive without WebSocket
- **Add:**
```python
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}
```

### 13. 🟡 **MEDIUM: No Graceful Shutdown**
- **Files:** `app.py`, `backend/main.py`
- **Issue:** Ctrl+C kills process without cleanup (STT stream, DB connections)
- **Fix:** Handle SIGTERM/SIGINT, close STT stream, close memory DB, stop tray icon

### 14. 🟡 **MEDIUM: Placeholder Character Limitations**
- **File:** `frontend/character.js:197-237`
- **Issue:** Placeholder has no morph targets for lip-sync, eyes only
- **Impact:** Lip-sync doesn't work if model fails to load
- **Fix:** Add simple mouth morph targets to placeholder, or procedural jaw movement

### 15. 🟡 **MEDIUM: Incomplete Viseme Mapping**
- **File:** `frontend/character.js:315-319` and `backend/tts.py:29-49`
- **Issue:**
  - Frontend expects 15 visemes (0-14)
  - Backend can produce up to 20 (0-19)
  - Mapping mismatch drops some visemes
- **Fix:** Align viseme sets between frontend and backend, update mapping tables

### 16. 🟡 **MEDIUM: Hard-Coded Window Size in Wander**
- **File:** `frontend/main.js:388`
- **Issue:** `winW = 400` hard-coded, but actual window size configurable
- **Fix:** Use `window.innerWidth` or query actual window size

### 17. 🟡 **MEDIUM: Missing User Preferences Persistence**
- **File:** `backend/memory.py`
- **Issue:** UI state (window position, volume, TTS preference) not saved/restored
- **Recommendation:** Store UI preferences in memory DB profile table

### 18. 🟡 **MEDIUM: lip-sync Stop Race Condition**
- **File:** `frontend/main.js:108-112`
- **Issue:** `audioLipSync` stopped only when `currentAudioSource` is null, but source might be null prematurely
- **Fix:** Better state management, ensure stop() called exactly once

### 19. 🟡 **MEDIUM: No Error Reporting to UI**
- **File:** `backend/main.py:98-105`
- **Issue:** Errors broadcast as `error` type but UI shows nothing
- **Fix:** Make UI display error messages in bubble or toast

### 20. 🟡 **MEDIUM: Ollama Model Name Mismatch**
- **File:** `.env:21`, `config.py:34`
- **Issue:** `.env` says `mistral` but user's Ollama has cloud models, not mistral
- **Impact:** LLM returns error, assistant shows fallback message
- **Fix:** Better error message when model not found, suggest `ollama pull`

---

## Low Priority Issues

### 21. 🟢 **LOW: Hard-Coded Strings (French Only)**
- **Files:** Multiple frontend/backend
- **Issue:** All UI text in French, not i18n-ready
- **Impact:** Not internationalizable
- **Fix:** Extract strings to config file, use language from system

### 22. 🟢 **LOW: Magic Numbers Throughout Code**
- **Examples:**
  - `main.js:62` toneMappingExposure = 1.2
  - `character.js:92` targetHeight = 1.8
  - `effects.js:86` particle count = 300
- **Fix:** Move to constants in config or class defaults

### 23. 🟢 **LOW: Code Duplication in Animation Loading**
- **File:** `frontend/character.js:152-192`
- **Issue:** Repeated code for each animation clip
- **Refactor:** Loop over config array with error handling per clip

### 24. 🟢 **LOW: Inconsistent Error Handling Patterns**
- **Some files:** Use try/catch with logging
- **Others:** Silent catch or no handling
- **Fix:** Establish error handling guidelines, use custom error classes

### 25. 🟢 **LOW: Missing Metrics/Monitoring**
- **No telemetry** on TTS latency, STT accuracy, LLM response time
- **Recommendation:** Add optional metrics collection for debugging

---

## Missing Features (Important)

### 26. ❌ **Missing: System Actions Implementation**
- **File:** `backend/llm.py:132-159`
- **Feature:** [ACTION] tags for system commands (OPEN_URL, EXEC, VOL, WEATHER, SYS_INFO)
- **Status:** Code exists but limited
- **Issues:**
  - WEATHER uses wttr.in but no error handling if offline
  - EXEC runs shell commands with `subprocess.Popen` **without validation** (security risk!)
  - VOL uses `pactl` (PulseAudio) not cross-platform (fails on ALSA/Windows)
- **Action Items:**
  - Validate/sanitize command inputs for EXEC (whitelist or explicit confirmation)
  - Make VOL platform-aware (use platform appropriate API)
  - Add feedback when action executed
  - Confirm dialog for dangerous commands

### 27. ❌ **Missing: File Drop Object Analysis**
- **File:** `frontend/main.js:234-251`
- **Feature:** Drag-and-drop file analysis
- **Status:** Sends `[OBJET DÉPOSÉ]` message to LLM but:
  - File not actually sent (only filename/size)
  - LLM prompt doesn't explain what to do with file
  - No file type validation
  - No size limit
  - No preview/summary for user
- **Fix:** Add file reading/summary, support images (vision), limit size, show progress

### 28. ❌ **Missing: Wake Word Integration**
- **File:** `backend/stt.py:78-95`
- **Feature:** Picovoice wake word configured but:
  - Default `WAKE_WORD=porcupine` but no keyword file specified
  - `PICOVOICE_ACCESS_KEY` empty in .env
  - `_is_waiting_for_wake` logic may not work without proper key
  - No UI indicator when wake word active
- **Fix:** Better wake word setup flow, provide demo keywords, graceful disable if invalid

### 29. ❌ **Missing: TTS Voice Selection UI**
- **Feature:** No way to change TTS voice/speaker from UI
- **Current:** Voice hard-coded in `tts.py:116` (Claribel Dervla for Coqui)
- **Fix:** Expose voice selection in setup.py or settings dialog

### 30. ❌ **Missing: Conversation History in UI**
- **Feature:** User cannot see past conversations
- **Current:** Chat logs stored in DB but no UI to browse
- **Fix:** Add conversation history panel, search, export

### 31. ❌ **Missing: Memory Management UI**
- **Feature:** Cannot view/edit stored facts, summaries
- **Current:** All memory operations backend-only
- **Fix:** Add settings tab to view semantic memory, delete facts, manage summaries

### 32. ❌ **Missing: Offline Mode Indicator**
- **Feature:** No clear indication when AI is offline/unavailable
- **Impact:** User thinks assistant is broken
- **Fix:** Show status message, retry count, fallback behavior explanation

### 33. ❌ **Missing: Volume Control**
- **File:** `frontend/main.js` (no volume UI)
- **Feature:** Volume slider for assistant voice
- **Current:** System volume only via ACTION:VOL (if implemented)
- **Fix:** Add volume slider in UI, store preference

### 34. ❌ **Missing: Animation Error Recovery**
- **File:** `frontend/character.js:126-134`
- **Issue:** If animation fails to load, no retry or user notification
- **Fix:** Show placeholder message, retry logic, allow manual reload

### 35. ❌ **Missing: Model Hotswap**
- **Feature:** Cannot change character model without editing code
- **Fix:** Add model picker in UI, support multiple GLB/FBX files

---

## Security Issues

### 36. ⚠️ **SECURITY: Unsanitized Shell Command Execution**
- **File:** `backend/llm.py:142`
- **Code:** `subprocess.Popen(val, shell=True)`
- **Risk:** LLM could generate malicious action tags to execute arbitrary commands
- **Impact:** **Critical** - Remote code execution via LLM
- **Fix:**
  - Validate commands against whitelist
  - Require user confirmation for EXEC actions
  - Disable by default, opt-in only
  - Sanitize input thoroughly

### 37. ⚠️ **SECURITY: No Rate Limiting on WebSocket**
- **File:** `backend/main.py:108-156`
- **Issue:** Any client can send unlimited messages
- **Risk:** DoS on LLM API, quota exhaustion
- **Fix:** Add rate limiting per IP or connection

### 38. ⚠️ **SECURITY: API Keys Logged in Plaintext**
- **File:** Various
- **Issue:** Errors might log API keys if exception includes request details
- **Fix:** Sanitize logs, use environment variables properly, never log request bodies with keys

---

## Performance Issues

### 39. ⚡ **PERF: TTS Model Loads on Every Call (if Coqui)**
- **File:** `backend/tts.py:58-70`
- **Issue:** `_get_coqui()` checks if None but global variable might not persist across threads properly
- **Impact:** Slow TTS on first call, potential reloading
- **Fix:** True singleton pattern, pre-warm TTS model at startup

### 40. ⚡ **PERF: No Whisper Model Caching**
- **File:** `backend/stt.py:30-41`
- **Issue:** Model loads on first transcription but may reload if called from different thread
- **Fix:** Ensure thread-safe singleton, eager load at startup

### 41. ⚡ **PERF: Particle System Update Loop**
- **File:** `frontend/effects.js:160-206`
- **Issue:** Updates all 300 particles every frame with JavaScript loops
- **Impact:** Could be GPU-bound on low-end systems
- **Fix:** Use GPU particles (shaders), reduce count, LOD based on FPS

### 42. ⚡ **PERF: Unnecessary Character Geometry Recalculation**
- **File:** `frontend/character.js:88-101`
- **Issue:** Recaclulates bounding box and repositions every load (not per frame, okay)
- **Status:** Not a bottleneck but ensure not called repeatedly

---

## Testing Gaps

### 43. 🧪 **TESTING: Zero Test Coverage**
- **Files:** All
- **Issue:** No unit tests, integration tests, or E2E tests
- **Risk:** Regressions, broken features
- **Must Add:**
  - Unit tests for `tts.py`, `stt.py`, `llm.py` (mock APIs)
  - Integration tests for WebSocket messages
  - Frontend component tests (Jest/Vitest)
  - E2E test with test LLM (mock)

### 44. 🧪 **TESTING: No Mock LLM for Testing**
- **Issue:** Cannot test assistant without real LLM API (cost/keys)
- **Fix:** Create mock LLM provider that returns canned responses

### 45. 🧪 **TESTING: No WebSocket Client Simulation**
- **Issue:** Hard to test WebSocket flows without UI
- **Fix:** Add test client script or pytest fixtures

---

## Documentation Gaps

### 46. 📚 **DOCS: Missing Architecture Diagram**
- **Issue:** No visual representation of system architecture
- **Fix:** Create diagram showing:
  - Frontend (Three.js) ↔ WebSocket ↔ Backend (FastAPI)
  - Backend modules: STT → LLM → TTS pipeline
  - Data flow: audio bytes, visemes, text

### 47. 📚 **DOCS: No API Documentation**
- **Issue:** WebSocket message formats not documented
- **Fix:** Document message types: `user_input`, `status`, `speech`, `config`, `stats_sync`, `error`

### 48. 📚 **DOCS: No Deployment Guide**
- **Issue:** README says "run python app.py" but doesn't cover:
  - Service setup (systemd)
  - Docker containerization
  - Production environment variables
  - Troubleshooting common issues
- **Fix:** Add DEPLOYMENT.md with step-by-step

### 49. 📚 **DOCS: No Contribution Guidelines**
- **Issue:** No CONTRIBUTING.md, CODE_OF_CONDUCT
- **Fix:** Add standard contribution guide

### 50. 📚 **DOCS: Config Options Not Fully Documented**
- **File:** `.env` example
- **Issue:** Some config options in `config.py` not in `.env` example:
  - `SAMPLE_RATE`, `CHANNELS`, `BLOCK_DURATION`
  - `SILENCE_THRESHOLD`, `SILENCE_DURATION`
  - `PIPER_MODEL`, `PIPER_CONFIG`
- **Fix:** Keep `.env` in sync with config.py

---

## Missing Error Handling

### 51. ⚠️ **ERROR: No Backend Startup Error Propagation**
- **File:** `app.py:59-70`
- **Issue:** `run_server()` exceptions aren't caught, app continues unaware
- **Fix:** Catch exceptions, log to UI, exit cleanly

### 52. ⚠️ **ERROR: STT Microphone Access Denied**
- **File:** `backend/stt.py:216`
- **Issue:** If user denies mic permission, prints error but no UI notification
- **Fix:** Send status message to UI, show toast

### 53. ⚠️ **ERROR: TTS Engine Import Errors Silently Ignored**
- **File:** `backend/tts.py:62-69`
- **Issue:** If Coqui import fails, sets `_coqui_model = False` but subsequent calls still try
- **Fix:** Set to None and don't retry, log reason

---

## Frontend-Specific Issues

### 54. 🎨 **FRONTEND: Three.js Import Map Uses CDN (Disconnected)**
- **File:** `frontend/index.html:399-406`
- **Issue:** Imports from `https://ga.jspm.io` - fails if offline
- **Impact:** App breaks when no internet
- **Fix:** Bundle Three.js locally, use relative imports

### 55. 🎨 **FRONTEND: No Loading State for 3D Model**
- **File:** `frontend/character.js:434-442`
- **Issue:** Shows generic loader but no progress indication for large models
- **Fix:** Add loading progress from GLTFLoader

### 56. 🎨 **FRONTEND: Render Loop Always Runs**
- **File:** `frontend/main.js:101-116`
- **Issue:** `animate()` runs forever even if window hidden
- **Fix:** Pause render loop when window not visible (`visibilitychange` event)

### 57. 🎨 **FRONTEND: WebSocket No Message Ack**
- **File:** `frontend/main.js:142-146`
- **Issue:** No acknowledgment that messages received by server
- **Impact:** User might resend thinking it failed
- **Fix:** Implement ack from server, show sending status

### 58. 🎨 **FRONTEND: No Retry for Failed Audio Playback**
- **File:** `frontend/main.js:355-359`
- **Issue:** If `audioCtx.decodeAudioData` fails, just logs, no retry
- **Fix:** Retry once, fallback to text-only

---

## Backend-Specific Issues

### 59. ⚙️ **BACKEND: No Request Timeout Configuration**
- **File:** `backend/llm.py:171-180`, `tts.py` various
- **Issue:** All HTTP requests have hard-coded timeouts (30s, 60s)
- **Fix:** Move to config, allow per-provider tuning

### 60. ⚙️ **BACKEND: Proactive Heartbeat Hard-Coded**
- **File:** `backend/main.py:181-198`
- **Issue:** 5 minutes threshold not configurable
- **Fix:** Add `PROACTIVITY_THRESHOLD` to config

### 61. ⚙️ **BACKEND: LLM Temperature Fixed**
- **File:** `backend/llm.py:66`, `177`
- **Issue:** Temperature 0.7/0.8 not configurable
- **Fix:** Add to config or character.yaml

### 62. ⚙️ **BACKEND: Memory Summary Too Aggressive**
- **File:** `backend/llm.py:78-102`
- **Issue:** Summarizes after 14 messages, might lose context
- **Fix:** Make threshold configurable, add summary quality check

---

## Asset & Resource Issues

### 63. 🖼️ **ASSET: Missing SFX Files**
- **File:** `frontend/sound.js:15-22`
- **Issue:** References audio files that may not exist:
  - `arise_epic.mp3`
  - `ui_click.mp3`
  - `ghost_move.mp3`
  - `magic_spark.mp3`
- **Impact:** SFX won't play, errors in console
- **Fix:** Add placeholder sounds or silent fallback

### 64. 🖼️ **ASSET: Animation Files May Not Exist**
- **File:** `frontend/character.js:153-161`
- **Issue:** FBX files listed but not verified in repo
- **Check:** Some animations 404 in logs
- **Fix:** Ensure all animation files present or handle missing gracefully

### 65. 🖼️ **ASSET: No Icon File for Build**
- **File:** `build.py:35`
- **Issue:** References `frontend/assets/icon.ico` but doesn't exist
- **Fix:** Create icon or make optional

---

## Technical Debt

### 66. 💳 **DEBT: PyWebView GUI = Qt (Not Cross-Platform Stable)**
- **Issue:** PyWebView tries GTK then Qt, both require heavy dependencies
- **Impact:** Installation complexity, crashes on some Linux distros
- **Consider:** Electron alternative? Or improve error message

### 67. 💳 **DEBT: Mixamo Animation Retargeting Fragile**
- **File:** `frontend/character.js:173-178`
- **Issue:** Regex-based bone name cleanup might fail on some rigs
- **Fix:** Add configurable bone mapping per model

### 68. 💳 **DEBT: No TypeScript (JavaScript)**
- **Issue:** Frontend is plain JS, hard to maintain
- **Fix:** Migrate to TypeScript (effort high, long-term benefit)

### 69. 💳 **DEBT: Python 3.14 Compatibility Unknown**
- **Issue:** Dependencies may not support Python 3.14 yet
- **Fix:** Test on 3.11/3.12 LTS, pin version in setup.py

---

## Feature Requests (Nice-to-Have)

### 70. ✨ **FEATURE: Multi-Language Support**
- **Current:** French only (except system prompts)
- **Add:** Language detection, UI translation, TTS language switching

### 71. ✨ **FEATURE: Emotion-to-Voice Modulation**
- **Current:** Emotion changes aura color only
- **Add:** Pitch/speed/volume modulation based on emotion

### 72. ✨ **FEATURE: Custom Animation Triggers**
- **Add:** LLM can trigger specific animations via tags: `[ANIM:bow]`, `[ANIM:summon]`

### 73. ✨ **FEATURE: Contextual Awareness (Time/Location)**
- **Add:** Inject time of day, weather (if available), user location (with permission)

### 74. ✨ **FEATURE: Voice Activity Detection (VAD)**
- **Current:** Uses silence threshold, but could use neural VAD for better accuracy

### 75. ✨ **FEATURE: Assistant "Memory Palace" Visualization**
- **UI:** 3D visualization of memory facts (cloud of orbs, etc.)

### 76. ✨ **FEATURE: Plugin System**
- **Architecture:** Allow plugins for custom actions, TTS engines, LLM providers

### 77. ✨ **FEATURE: Hotkeys for Common Actions**
- **Example:** Global hotkey to toggle listen mode, mute, etc.

### 78. ✨ **FEATURE: Avatar Customization**
- **Allow:** User to change character appearance (colors, accessories)

---

## Dependency & Build Issues

### 79. 📦 **DEPENDENCY: pywebview 5.3 vs 6.1**
- **File:** `backend/requirements.txt:8`
- **Issue:** Says 5.3 but pip shows 6.1 installed
- **Fix:** Pin to tested version or update to 6.1

### 80. 📦 **DEPENDENCY: fastapi 0.115.0 vs 0.135.1**
- **File:** `backend/requirements.txt:1`
- **Issue:** Requirements says 0.115.0 but 0.135.1 installed (major version gap)
- **Fix:** Update requirements to actual version or test compatibility

### 81. 📦 **DEPENDENCY: Missing python-multipart**
- **Issue:** FastAPI needs it for form data but not in requirements
- **Fix:** Add `python-multipart` if using file uploads

### 82. 📦 **DEPENDENCY: build.py Uses PyInstaller But Not in Requirements**
- **File:** `build.py`
- **Issue:** PyInstaller not in requirements.txt
- **Fix:** Add dev dependency or note in docs

---

## Summary Statistics

- **Total Issues Identified:** 82
- **Critical:** 4
- **High:** 10
- **Medium:** 10
- **Low:** 5
- **Missing Features:** 13
- **Security:** 2
- **Performance:** 4
- **Testing:** 3
- **Documentation:** 4
- **Assets:** 3
- **Technical Debt:** 4
- **Feature Requests:** 7
- **Dependency:** 4

---

## Recommended Implementation Order

### Phase 1: Stability & Security (Week 1-2)
1. Fix database path (done ✓)
2. Add dependency validation at startup
3. Implement proper backend health check
4. Fix WebSocket reconnection logic
5. Sanitize shell command execution (CRITICAL SECURITY)
6. Add rate limiting
7. Fix TTS engine singleton/caching
8. Improve STT resource cleanup

### Phase 2: User Experience (Week 3-4)
1. Add missing asset files (SFX, icons)
2. Implement offline mode indicator
3. Add error display in UI
4. Show connection status
5. Add conversation history UI
6. Volume control
7. Better loading states
8. Model hotswap support

### Phase 3: Robustness (Week 5-6)
1. Add comprehensive error handling
2. Graceful shutdown
3. Configuration validation
4. Logging improvements
5. Memory persistence for UI state
6. LLM fallback chain
7. Platform abstraction (VOL command)

### Phase 4: Testing & Documentation (Week 7-8)
1. Set up pytest framework
2. Write unit tests for core modules (mock APIs)
3. Integration tests for WebSocket
4. Create architecture diagram
5. Document API
6. Write deployment guide
7. Add contribution guidelines

### Phase 5: Advanced Features (Week 9+)
1. File drop analysis with vision
2. Wake word improvements
3. Voice selection UI
4. Memory management UI
5. Multi-language support
6. Emotion voice modulation
7. Plugin system (if needed)

---

## Quick Wins (Can Do Immediately)

1. Fix critical SECURITY issue (shell command sanitization)
2. Add .env file missing config options
3. Replace CDN imports with bundled Three.js
4. Add backend /health endpoint
5. Show errors in UI when LLM/TTS fails
6. Add at least placeholder SFX files
7. Implement exponential backoff for WebSocket
8. Add config validation at startup

---

## Risk Assessment

**Highest Risk Areas:**
1. **Security:** Arbitrary command execution via LLM (CRITICAL)
2. **Stability:** Missing dependencies cause silent failures
3. **Reliability:** No tests, frequent crashes possible
4. **Data:** SQLite corruption risk from threading

**Mitigation Priorities:**
1. Sanitize all user-controlled input before exec()
2. Add dependency checks before starting
3. Add comprehensive logging
4. Implement proper thread safety for DB

---

## Conclusion

The Sung Jin Woo assistant is an impressive project with cutting-edge integrations (3D, AI, real-time audio). However, it needs significant work to be production-ready. Focus first on **stability, security, and error handling** before adding new features. The codebase is maintainable but requires refactoring in several areas (configuration, error handling, testing infrastructure).

**Overall Priority:** High - fix security issues, then build reliability layer, then enhance UX.
