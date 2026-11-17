# HyperCore evidence-provenance glyph | asset manifest

- **Name:** `evidence-provenance.svg` (HyperCore evidence checkpoint).
- **Purpose:** Reusable source-ready icon for the Command Center's evidence ledger, diagnostics reports and build verification *entry points*. A check-shaped marker means an evidence checkpoint exists, **not** that external verification passed.
- **Dimensions:** 96 × 96 SVG viewBox; recommended display 24, 32, 48 or 64 CSS pixels; preserve 1:1 aspect ratio. Minimum display 24 px; use text labels at smaller sizes.
- **Colors:** background `#101722`, blue `#0078FF`, cyan `#35D5FF`, gear outline `#24476D`, orange checkpoint `#FF7A00`. Existing HyperCore palette reused from `index.html`; no new token introduced.
- **Style:** dark engineering; cubic blue module, mechanical gear ring, restrained orange evidence node. No embedded raster, script, animation, external asset or font dependency.
- **Accessibility:** SVG has `role="img"`, `title` and `desc`; when paired with an explicit text label, render as decorative with `aria-hidden="true"` in the consuming UI. Never convey verified status by color or icon alone.
- **Status:** repository-integrated *source asset on the existing draft PR #114 branch*, **not merged, shipped, Android-tested or deployed**. SVG source-level static review only until independent render/DOM inspection.
- **License / branding:** Original project-specific vector design drafted for Selma°; repository licensing and final trademark/brand ownership must be checked before public redistribution. No third-party logos or proprietary icon fonts incorporated.
- **Reference:** `apps/selma-hypercore/index.html`, `apps/selma-hypercore/README.md`; review [PR #114](https://github.com/Spiritjcrow/Selma.0/pull/114).
- **Next safe action:** Render SVG in a browser at 24/32/64 px, inspect light/dark contrast and screen-reader labeling, then wire it to the *recorded evidence* affordance on the existing proof ledger in a separate reviewed change. Do not infer machine verification or start an APK build from the icon.

## Integration checkpoint: preflight v0.3
- Source icon is now referenced by `apps/selma-hypercore/preflight.html` at 72 CSS px with empty `alt` because adjacent header text names the function.
- The icon represents **evidence capture/inspection**, NOT verified authenticity, completed jobs, signed code, or successful device installation.
- `node --test tests/preflight.test.cjs` 32/32 PASS locally for checkpoint logic; **browser rendering not yet verified**, so no accessibility sign-off.
- See [implementation checklist](../docs/preflight-25.md) and [draft PR #114](https://github.com/Spiritjcrow/Selma.0/pull/114). No merge or release.
