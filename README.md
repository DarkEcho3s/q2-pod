<p align="center">
  <a href="https://youtu.be/C5x05EwsPGI" title="Watch the Q2 Pod video on YouTube">
    <img src="assets/banner.png" alt="Q2 Pod: the iPod firmware mod for the Shanling Q2" width="100%">
  </a>
</p>

<p align="center">
  An iPod classic style firmware mod for the Shanling Q2.<br>
  Wheel navigation, parametric EQ and Coverflow, built on the stock firmware.
</p>

<p align="center">
  <a href="https://github.com/DiamondBond/q2-pod/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/DiamondBond/q2-pod?style=flat-square&label=release&color=3D424B"></a>
  <a href="#features"><img alt="Device: Shanling Q2" src="https://img.shields.io/badge/device-Shanling%20Q2-B99AC8?style=flat-square"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-D77868?style=flat-square"></a>
  <a href="https://youtu.be/C5x05EwsPGI"><img alt="Watch on YouTube" src="https://img.shields.io/badge/YouTube-video-FF0000?style=flat-square&logo=youtube&logoColor=white"></a>
  <a href="https://discord.gg/pgsQpXhSQ"><img alt="Join the Discord" src="https://img.shields.io/badge/Discord-join-5865F2?style=flat-square&logo=discord&logoColor=white"></a>
</p>

<p align="center">
  <b><a href="https://github.com/DiamondBond/q2-pod/releases/latest">Download</a></b> ·
  <b><a href="#install">Install</a></b> ·
  <b><a href="docs/guide.md">User guide</a></b> ·
  <b><a href="docs/changelog.md">Changelog</a></b>
</p>

## Features

- **iPod UI:** Home, lists, Now Playing, Coverflow and four visualizers, with your choice of accent, Home layout and battery display.
- **Wheel navigation:** ticks follow your finger, and menus remember your place.
- **Parametric EQ:** up to 30 bands, a live curve, and AutoEQ / Equalizer APO preset imports.
- **Spotify Connect:** the Q2 becomes a Spotify speaker (Premium required).
- **Internet Radio:** your own stations plus the [radio-browser.info](https://www.radio-browser.info) directory.
- **Scrobbling:** send listens to Last.fm or ListenBrainz over Wi-Fi.
- **Battery options:** an optional 80% charge limit, Low power mode and a sleep timer.
- **Also includes:** favourites, playlists, Most Played, shuffle by song, album or folder, Crossfade, podcasts and audiobooks that resume where you stopped, and fixes for choppy AirPods AAC audio and the clock resetting after power-off.

Prefer the stock look? Download `Q2.Firmware.*-stock.zip`. It has the same features and fixes, without the iPod UI.

## Install

> [!IMPORTANT]
> Charge the Q2 first, and leave the microSD card in until the update finishes. Only remove or insert the card with the Q2 fully shut down (not asleep), or it can corrupt the card.

1. [Download the latest release](https://github.com/DiamondBond/q2-pod/releases/latest), unzip `Q2.Firmware.*.zip`, and copy `update.tar` to the microSD card's root.
2. On the Q2, open **System settings → System Update → TF card update**.
3. After the restart, **System settings → About** shows FW V1.32 and your **CFW. Version**.

The updater skips a build that's already installed, so updating to a newer release always works.

**Restore stock:** flash the [official Shanling firmware](https://en.shanling.com/download/150) the same way. If the UI won't start, copy the `recovery-update` folder from [Shanling's recovery package](https://drive.google.com/file/d/1aINQfJu6n0JTQ4hOzzD1uSpSj3TS_NJj/view?usp=drive_link) to the card, then hold previous-song and power on with the centre button.

## Optional add-ons

- **Rockbox:** unzip [Rockbox's `rockbox.zip`](https://github.com/DiamondBond/q2-rockbox/releases) to the card's root. Hold Play/Pause while powering on to use Q2 Pod for that session. See the [setup guide](docs/setup.md) and [ported themes](https://github.com/DiamondBond/q2-rockbox-themes/releases).
- **Spotify:** unzip `q2-librespot-*.zip` from [q2-librespot's latest release](https://github.com/DiamondBond/q2-librespot/releases/latest) to the card's root, then open **Streaming → Spotify** on the Q2 and pick it in the Spotify app. See the [guide](docs/guide.md#spotify).

## Everyday use

| Control                   | Action                                                                   |
| ------------------------- | ------------------------------------------------------------------------ |
| **Wheel**                 | Scroll. Spin faster to speed up. Change a setting when a slider is open. |
| **Centre**                | Open the selected item. Double-press to turn the screen off.             |
| **Hold Play/Pause**       | Open the track, queue, playlist and shuffle/repeat options.              |
| **Hold Return** (iPod UI) | Jump to Now Playing.                                                     |

Run **Library → Update Local Music** after adding music. The [user guide](docs/guide.md) covers all [controls](docs/guide.md#controls), [EQ](docs/guide.md#parametric-eq), [Coverflow](docs/guide.md#coverflow) and [tips](docs/guide.md#tips).

## Set up your card

Put any of these folders at the microSD card's root, and each adds a Library entry: `Podcasts/`, `Audiobooks/`, `Photos/`, `Books/`, `Videos/` and `EQ/` (for AutoEQ / Equalizer APO presets). See the [microSD card guide](docs/guide.md#microsd-card) for formats.

Settings, play counts and resume points live on the Q2, so they stay with the device. For scrobbling, see [set up scrobbling](docs/guide.md#set-up-scrobbling).

## Known limitations

- **Library size:** Update Local Music adds up to 65,000 songs.
- **Bluetooth:** skipping tracks can stutter on some headphones (AAC and LDAC), and AirPods' tap controls don't reach the Q2.
- **Crossfade:** only between songs from different albums, with **Gapless** on.
- **Lock screen:** black until you add your own [images](docs/guide.md#lock-screen).

See the [changelog](docs/changelog.md) for the full list of changes and known issues.

## Documentation

- [User guide](docs/guide.md): settings, controls, playback, media and scrobbling
- [Setup](docs/setup.md): Q2 Pod, Rockbox and themes on a fresh Q2
- [Changelog](docs/changelog.md): what's changed in each release
- [Building](docs/building.md) · [Releasing](docs/releasing.md) · [Internals](docs/internals.md)

## Contributing

Found a bug? [Open an issue](https://github.com/DiamondBond/q2-pod/issues) with the screen and the steps to reproduce it. To build it yourself, see [Building](docs/building.md).

## License

[MIT](LICENSE) covers this repository's code and docs. The Shanling firmware used in release images remains Shanling's. Q2 Pod is not affiliated with Shanling.
