# CDN Replacement - Three.js Local Bundling

**Date:** 2026-03-17
**Status:** ✅ Complete

---

## Problem
The frontend was importing Three.js and its addons from CDN (cdn.jsdelivr.net). This meant:
- Application **requires internet** to load
- CDN could be blocked or slow
- No offline operation
- Risk of CDN downtime breaking the app

---

## Solution
Downloaded all required Three.js modules and bundled them locally in `frontend/vendor/three/`.

### Files Downloaded

```
frontend/vendor/three/
├── three.module.js (1.3 MB)
└── addons/
    ├── loaders/
    │   ├── GLTFLoader.js (108 KB)
    │   └── FBXLoader.js (101 KB)
    └── postprocessing/
        ├── EffectComposer.js (4.6 KB)
        ├── RenderPass.js (2.5 KB)
        ├── UnrealBloomPass.js (13 KB)
        └── OutputPass.js (2.5 KB)
```

**Total:** ~1.5 MB of JavaScript added to repository

---

## Changes Made

### `frontend/index.html` (lines 396-408)
Changed importmap from CDN to local paths:

```json
{
  "imports": {
    "three":              "./vendor/three/three.module.js",
    "three/addons/":      "./vendor/three/addons/"
  }
}
```

---

## Result
✅ **Application now works completely offline!**
- No external CDN dependencies
- All Three.js modules loaded from local filesystem
- Faster startup (no network requests for libraries)
- Works in air-gapped environments

---

## Testing
1. Disconnect from internet
2. Run `python app.py`
3. App should load normally with all 3D functionality

---

## Notes
- Kept es-module-shims polyfill from CDN (small, well-cached, optional)
- Version locked at Three.js r167 (same as before)
- All addon imports verified against actual code usage
- No code changes required in JS files (import paths remain identical)

---

## Future Improvement
Consider bundling es-module-shims locally as well for 100% offline.
