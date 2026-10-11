A previous agent produced the plan below to accomplish the user's task. Implement the plan in a fresh context. Treat the plan as the source of user intent, re-read files as needed, and carry the work through implementation and verification.

# Album favourites and ratings in Coverflow

## Summary

Add **Add/Remove from Favourites** and **Rate album** to Hold Play/Pause on a Coverflow album, including **Artist → albums → Coverflow**. Album ratings are independent of song ratings. No new browsing screen.

## Implementation

- Extend the existing album context menu in `patch/navigation.c`, preserving queue, shuffle and artist actions. Display the current hearts beside **Rate album**.
- Reuse the five-heart picker: wheel selects 0–5, Centre or a heart tap saves, Return cancels. Allow it to belong to Coverflow without requiring Now Playing to be open or disturbing its heart controls.
- Follow song semantics: **5 hearts = favourite**, 1–4 = rated, 0 = unrated. Adding a favourite sets 5; removing it sets 0.
- Persist album ratings separately in `/mnt/data/ringnav-album-ratings`, using the existing atomic blob-write pattern and 4,096-entry capacity. Report capacity or write failures without claiming success; restore the prior in-memory value on failed saves.
- Add an internal album identity helper alongside `album_cmp` in `patch/coverflow.c`. Hash the same normalized album name and album-artist/folder identity used for grouping, including multi-disc folder normalization. Keep artwork keys unchanged. The synthetic **Unknown Album** card gets one aggregate identity.
- Revalidate the selected album before opening or saving; cancel safely if the page, selection or library changes. Clear picker state when its owning page closes.
- Update the guide, internal storage documentation and 1.1.2 checklist while preserving existing uncommitted work.

## Validation

- Extend `test/patch.py` for both Stock and iPod: main and artist Coverflow menus, favourite toggling, every rating, cancellation, reopening and reboot persistence.
- Verify album changes never alter song ratings, My Fav, song Ratings lists or Skip disliked behavior.
- Cover identically named albums by different artists/folders, compilations, multi-disc albums, case normalization and Unknown Album.
- Exercise full storage, malformed/truncated data, failed writes, selection changes and page destruction. Confirm Sort/Refresh cards expose no album actions and held-button release never toggles playback.
- Build both variants and run the existing patch checks. Add a device checklist for picker controls and returning to the artist view.

## Defaults and limits

- These actions apply to Coverflow album cards; grid menus and track-row menus remain outside this change.
- Album identities survive rescans; changing identity-defining tags or folders creates a new identity.
- Skipped: saved-album collections, new screens and dependencies. Hardware behavior remains unverified until tested on a Q2.
