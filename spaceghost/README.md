# SpaceGhost EarthWatch

A scheduled, **metadata-only** Earth imagery catalog monitor for the approximate Aransas Pass, Texas missing-pet search area.

## State

- Geographic center: 27.9359629 N, 97.1286663 W (approximate geocoded point, NOT a surveyed parcel).
- Radius: 1,300 m. Change the `CENTER` / `RADIUS_METERS` constants in `watch.py` for another area.
- Rolling acquisition window: 42 days. New scenes are deduplicated by collection and scene ID.
- Queries two independent public metadata catalogs: Element 84 Earth Search and Microsoft Planetary Computer STAC.
- Monitors Sentinel-2, Landsat Collection 2, and NAIP where those catalogs offer data. Sources may overlap and can have ingestion delays.
- Daily GitHub Actions job, normally 11:29 UTC; separate from ChatGPT scheduled tasks.
- Commits `spaceghost/state.json` and `spaceghost/latest.md` on successful runs.
- Opens one private-repository GitHub issue when **new** NAIP scenes or low-cloud scenes are discovered. GitHub Mobile notifications depend on account/repository notification settings.
- Existing imagery dates are retained. A new catalog entry is not necessarily newly acquired imagery.

## Run and verify

GitHub: Actions > SpaceGhost EarthWatch > Run workflow. A workflow may not run if GitHub Actions is disabled or billing/minutes are unavailable.

Run locally with Python 3 (only standard library):

```bash
python3 spaceghost/watch.py
```

To test without internet access:

```bash
python3 -m py_compile spaceghost/watch.py
```

The runner has `contents:write` and `issues:write` in this private repository; no personal access token or subscription is required for public catalog metadata. The workflow's default `GITHUB_TOKEN` cannot automatically send email from a Gmail account. No other external messaging credentials are configured.

## Imagery update requests

Google Earth provides an official imagery update request under **Help > Request imagery update**. Documentation:
https://developers.google.com/maps/documentation/earth/tell-us-about-a-problem

The provider uses reports to prioritize future imagery but does not guarantee capture, updates, responses, or a schedule. No public programmatic imagery-request API has been verified; automated web-form entry, impersonation, CAPTCHA circumvention, mass email or repeated requests are deliberately **not** implemented. The latest report contains a reusable, truthful request draft for one provider-approved submission.

## Interpretation safeguards

- Sentinel-2 optical pixels are generally 10-60 meters, Landsat optical pixels mostly ~30 meters; both are inadequate for reliably detecting an individual pet, person, or bird.
- NAIP imagery is higher-resolution and irregularly refreshed, and even aerial imagery is not live. LiDAR, existing site maps and historic elevation data stay distinct from new optical images.
- No live UAV, ground sensors, thermal sensors, moving-target tracking, private-property observation, or person-identification capability is implied.
- Date is the scene **acquisition** timestamp, not the catalog **publication** time, nor a verified ground observation.
- No guarantee of uninterrupted execution: GitHub runs can be delayed or disabled; APIs may be unavailable or apply limits. Failures remain visible in the Actions run logs.
- Don't release sensitive search coordinates to a public repository without checking them.

## Future expansions

Add provider-approved event feeds/webhooks and authentic opt-in push/email transport through repository secrets. Only enable outbound requests after confirming recipient, rate limits, source terms and authentication. Add an AOI-specific imagery quality checker when georeferenced pixel downloads are licensed and available.

Current scheduler and catalog updates are independent of the ChatGPT task queue.
