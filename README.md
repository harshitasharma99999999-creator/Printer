# Grand Forno Reels & Shorts Automation

GitHub-only daily automation for promoting Grand Forno fruit bowls on
[Instagram (`grand_forno`)](https://www.instagram.com/grand_forno/) and
[YouTube (`@fornogrand`)](https://www.youtube.com/@fornogrand). There is no
website, dashboard, server, or persistent worker. GitHub Actions generates,
renders, publishes, records links, and commits structured logs.

At 7:00 PM India time every day, `.github/workflows/daily-post.yml`:

1. Picks the least recently posted item from `data/menu_items.json`.
2. Generates safe sales copy and metadata with the OpenAI Responses API.
3. Generates Indian-English narration with ElevenLabs.
4. Uses the configured presenter mode: HeyGen when paid avatar credits are
   available, or the free branded presenter/visual fallback.
5. Renders a 1080×1920, 20–35 second MP4 with FFmpeg, product imagery,
   burned-in subtitles, benefits, branding, CTA, and order-link end screen.
6. Uploads through YouTube Data API `videos.insert` and Instagram. Instagram
   can use Upload-Post's OAuth-based connector, the official Meta Graph API, or
   the accepted-risk `instagrapi` fallback.
7. Commits platform results and uploaded links to `data/post_history.json` and
   timestamped JSONL files in `logs/`.

If Instagram permissions, account eligibility, checkpoints, or publishing fail,
the workflow still succeeds for YouTube and saves `grand-forno-reel.mp4`,
`caption.txt`, and `manual-post.json` in the workflow artifact under
`output/<run-id>/instagram-manual/`.

## Repository layout

```text
data/menu_items.json              menu facts and order URLs
data/post_history.json            committed upload history and links
assets/logo.png                   Grand Forno branding
assets/music/                     optional licensed music
assets/product_images/            <item-id>.png/jpg or default image
scripts/generate_script.py        OpenAI copy adapter
scripts/generate_voice.py         ElevenLabs voice adapter
scripts/generate_video.py         HeyGen + FFmpeg render pipeline
scripts/post_youtube.py           YouTube resumable upload
scripts/post_instagram.py         Instagram resumable upload + fallback
scripts/update_history.py         atomic history update
scripts/main.py                   daily orchestrator
.github/workflows/daily-post.yml  schedule and manual trigger
```

Product image filenames should match each menu `id`, for example
`assets/product_images/muscle-builder-bowl.jpg`. For production publishing,
each menu item must have its own visual at
`assets/product_images/<item-id>.png` or `.jpg`. The live workflow now fails
instead of silently publishing the same default visual for every item. Dry runs
may still use the default fallback for local testing.

Background music is loaded from `assets/music/` or from `BACKGROUND_MUSIC_PATH`
when set. The included `assets/music/fresh-upbeat-loop.wav` is a generated,
royalty-free loop and is mixed quietly under narration with fade-in/fade-out.

## One-time setup

Fork or push this repository to GitHub, then enable Actions. In
**Settings → Secrets and variables → Actions → Secrets**, add:

| Secret | Purpose |
|---|---|
| `OPENAI_API_KEY` | Marketing script, caption, title, and overlays |
| `VOICE_API_KEY` | ElevenLabs text-to-speech |
| `AVATAR_API_KEY` | HeyGen presenter generation |
| `YOUTUBE_CLIENT_ID` | Google OAuth client |
| `YOUTUBE_CLIENT_SECRET` | Google OAuth client |
| `YOUTUBE_REFRESH_TOKEN` | Refresh token with `youtube.upload` scope |
| `UPLOAD_POST_API_KEY` | Upload-Post API key for Instagram publishing |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Meta token for official Graph API; optional when Upload-Post is used |
| `INSTAGRAM_ACCOUNT_ID` | Instagram professional account ID for official Graph API; optional when Upload-Post is used |
| `GRAND_FORNO_INSTAGRAM_USERNAME` | Last-resort private API fallback username |
| `GRAND_FORNO_INSTAGRAM_PASSWORD` | Last-resort private API fallback password |
| `GRAND_FORNO_INSTAGRAM_SESSION_JSON` | Preferred private API session JSON after local verification |

Under the adjacent **Variables** tab add:

| Variable | Purpose |
|---|---|
| `AVATAR_ID` | A realistic female presenter/avatar ID available to the HeyGen account |
| `VOICE_ID` | ElevenLabs voice ID; optional, defaults locally to a female voice |
| `UPLOAD_POST_USER` | Upload-Post connected profile/user identifier, for example `grand-forno` |

Current Instagram setup uses Upload-Post because Grand Forno's Facebook account
is disabled and the direct private API login is being blocked by Instagram:

```yaml
INSTAGRAM_PROVIDER: upload_post
UPLOAD_POST_USER: ${{ vars.UPLOAD_POST_USER }}
UPLOAD_POST_API_KEY: ${{ secrets.UPLOAD_POST_API_KEY }}
```

Create/connect the Instagram profile inside Upload-Post, generate an API key,
then save the key as the `UPLOAD_POST_API_KEY` GitHub secret and the connected
profile identifier as the `UPLOAD_POST_USER` GitHub variable. The Upload-Post
adapter sends the rendered MP4 to `POST /api/upload` with
`platform[]=instagram`, `media_type=REELS`, `share_to_feed=true`, and the
Grand Forno caption.

The other official option is Meta Graph API: the Instagram account must be a
Business or Creator account connected to a Facebook Page, and the token needs
the current content-publishing permissions. Use a long-lived token and renew it
before expiry. Instagram upload is binary and resumable; no public video host is
required.

If you intentionally switch back to the private API fallback, configure:

```yaml
INSTAGRAM_PROVIDER: instagrapi
INSTAGRAM_MODE: auto
```

This fallback is unofficial and can trigger Instagram checkpoints, temporary
locks, or account disablement. For the safest private fallback, generate a
verified session on your own computer:

```powershell
pip install instagrapi
python scripts/gen_instagram_session.py
```

Complete any OTP/challenge that Instagram asks for, then save the produced JSON
as the `GRAND_FORNO_INSTAGRAM_SESSION_JSON` GitHub secret. If you skip session
JSON, the workflow can use `GRAND_FORNO_INSTAGRAM_USERNAME` and
`GRAND_FORNO_INSTAGRAM_PASSWORD`, but that is more likely to trigger a
checkpoint from GitHub's servers. Never paste passwords into chat or commit them
to Git.

For YouTube, enable YouTube Data API v3 in Google Cloud, configure OAuth
consent, and generate a refresh token for the channel with
`https://www.googleapis.com/auth/youtube.upload`. Google may force uploads from
an unaudited API project to private even though the workflow requests `public`.
Complete Google’s API audit if that restriction applies.

The workflow requests write access only to commit `data/post_history.json` and
`logs/`. In **Settings → Actions → General → Workflow permissions**, allow
**Read and write permissions**. Branch protection must permit the bot push, or
the commit step must be adapted to open a pull request.

## Run and verify

Start with **Actions → Grand Forno Daily Reel and Short → Run workflow** and
enable `dry_run`. Dry-run mode makes no social API calls and uploads the video
plus manual-post package as a GitHub Actions artifact.

For local validation:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-grand-forno.txt
python scripts/main.py --dry-run --allow-fallback
```

Windows activation is `.\venv\Scripts\activate`. Install FFmpeg/ffprobe and
`espeak-ng` first for the credential-free fallback. Copy `.env.example` to
`.env` only for local work; never commit `.env` or real keys.

After inspecting the 9:16 render, add production secrets and run without
`dry_run`. The normal schedule is `30 13 * * *`, exactly 19:00 IST because
India does not observe daylight saving time.

## Content controls and operations

- Menu claims come from `data/menu_items.json`; review calories, protein,
  serving sizes, and prices before launch.
- Item selection avoids recent repeats using `GRAND_FORNO_NO_REPEAT_WINDOW`
  (default `4`, so with five menu items it rotates through the menu before
  returning to an item). When an item eventually cycles back, the copy generator
  uses a different creative angle so the post is not a duplicate.
- Copy validation rejects unsafe phrases and requires both exact ordering URLs
  and all required hashtags.
- Set `INSTAGRAM_MODE=manual` to force the manual package.
- Set `INSTAGRAM_PROVIDER=meta_graph` when the Facebook/Meta account is
  recovered and official Instagram publishing credentials are ready.
- Set `INSTAGRAM_PROVIDER=upload_post` for Upload-Post OAuth-based publishing.
- Set `INSTAGRAM_PROVIDER=instagrapi` only for the accepted-risk private API
  fallback.
- Set `AVATAR_MODE=visual` to use the branded fruit-visual fallback without
  consuming HeyGen credits; use `auto` to enable the realistic presenter.
- Set `BACKGROUND_MUSIC_PATH` to a different owned/licensed music file if you
  want to change the daily Reel/Short music.
- Live Actions disable generation fallbacks so a missing voice/avatar cannot
  silently publish an unintended presenter-free ad. Explicit visual mode is
  recorded in each run manifest.
- Videos and audio stay in 30-day Actions artifacts rather than bloating Git.
  Durable upload URLs and statuses are committed in post history.
- Use only owned/licensed product photos and music. Optional music files are
  intentionally not mixed by default until rights and loudness are reviewed.
- The generated realistic avatar is disclosed to YouTube with
  `containsSyntheticMedia=true`.

Sample output is in `examples/sample_script.txt` and
`examples/sample_caption.txt`.

---

# MoneyPrinter V2
 
> ♥︎ **Sponsor**: The Best AI Chat App: [shiori.ai](https://www.shiori.ai). Use code **MPV2** for 20% off.

---

> 𝕏 Also, follow me on X: [@DevBySami](https://x.com/DevBySami).

[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/FujiwaraChoki/MoneyPrinterV2)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-brightgreen?logo=buymeacoffee)](https://www.buymeacoffee.com/fujicodes)
[![GitHub license](https://img.shields.io/github/license/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/issues)
[![GitHub stars](https://img.shields.io/github/stars/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/stargazers)
[![Discord](https://img.shields.io/discord/1134848537704804432?style=for-the-badge)](https://dsc.gg/fuji-community)

An Application that automates the process of making money online.
MPV2 (MoneyPrinter Version 2) is, as the name suggests, the second version of the MoneyPrinter project. It is a complete rewrite of the original project, with a focus on a wider range of features and a more modular architecture.

> **Note:** MPV2 needs Python 3.12 to function effectively.
> Watch the YouTube video [here](https://youtu.be/wAZ_ZSuIqfk)

## Features

- [x] Twitter Bot (with CRON Jobs => `scheduler`)
- [x] YouTube Shorts Automater (with CRON Jobs => `scheduler`)
- [x] Affiliate Marketing (Amazon + Twitter)
- [x] Find local businesses & cold outreach

## Versions

MoneyPrinter has different versions for multiple languages developed by the community for the community. Here are some known versions:

- Chinese: [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)

If you would like to submit your own version/fork of MoneyPrinter, please open an issue describing the changes you made to the fork.

## Installation

> ⚠️ If you are planning to reach out to scraped businesses per E-Mail, please first install the [Go Programming Language](https://golang.org/).

```bash
git clone https://github.com/FujiwaraChoki/MoneyPrinterV2.git

cd MoneyPrinterV2
# Copy Example Configuration and fill out values in config.json
cp config.example.json config.json

# Create a virtual environment
python -m venv venv

# Activate the virtual environment - Windows
.\venv\Scripts\activate

# Activate the virtual environment - Unix
source venv/bin/activate

# Install the requirements
pip install -r requirements.txt
```

## Usage

```bash
# Run the application
python src/main.py
```

## Documentation

All relevant document can be found [here](docs/).

## Scripts

For easier usage, there are some scripts in the `scripts` directory, that can be used to directly access the core functionality of MPV2, without the need of user interaction.

All scripts need to be run from the root directory of the project, e.g. `bash scripts/upload_video.sh`.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us. Check out [docs/Roadmap.md](docs/Roadmap.md) for a list of features that need to be implemented.

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

MoneyPrinterV2 is licensed under `Affero General Public License v3.0`. See [LICENSE](LICENSE) for more information.

## Acknowledgments

- [KittenTTS](https://github.com/KittenML/KittenTTS)
- [gpt4free](https://github.com/xtekky/gpt4free)

## Disclaimer

This project is for educational purposes only. The author will not be responsible for any misuse of the information provided. All the information on this website is published in good faith and for general information purpose only. The author does not make any warranties about the completeness, reliability, and accuracy of this information. Any action you take upon the information you find on this website (FujiwaraChoki/MoneyPrinterV2), is strictly at your own risk. The author will not be liable for any losses and/or damages in connection with the use of our website.
