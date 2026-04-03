import os
import subprocess
import requests
from datetime import datetime

from config import ROOT_DIR, get_verbose
from status import info, warning, success


class Podcast:
    """
    Spotify Podcast automation via GitHub Releases + RSS.
    Flow: WAV → MP3 → GitHub Release (free CDN) → update podcast/feed.xml → push.
    One-time: user submits the RSS URL to Spotify for Podcasters.
    """

    RSS_PATH = os.path.join(ROOT_DIR, "podcast", "feed.xml")

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "").strip()
        self.repo = os.environ.get("GITHUB_REPOSITORY", "").strip()  # "owner/repo"

    @property
    def _owner(self) -> str:
        return self.repo.split("/")[0] if "/" in self.repo else ""

    @property
    def _repo_name(self) -> str:
        return self.repo.split("/")[1] if "/" in self.repo else ""

    def _to_mp3(self, wav_path: str) -> str:
        mp3_path = wav_path.replace(".wav", "-podcast.mp3")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path,
             "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
            capture_output=True,
        )
        if result.returncode == 0:
            return mp3_path
        if get_verbose():
            warning(f"Podcast: MP3 conversion failed: {result.stderr.decode()[:200]}")
        return ""

    def _create_github_release(self, tag: str, title: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        r = requests.post(
            f"https://api.github.com/repos/{self.repo}/releases",
            headers=headers,
            json={
                "tag_name": tag,
                "name": f"Podcast: {title[:80]}",
                "body": title,
                "draft": False,
                "prerelease": False,
            },
            timeout=20,
        )
        if r.ok:
            return r.json()
        if get_verbose():
            warning(f"Podcast: GitHub release failed {r.status_code} {r.text[:200]}")
        return {}

    def _upload_mp3(self, upload_url: str, mp3_path: str) -> str:
        filename = os.path.basename(mp3_path)
        clean_url = upload_url.split("{")[0]
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "audio/mpeg",
        }
        with open(mp3_path, "rb") as f:
            r = requests.post(
                f"{clean_url}?name={filename}",
                headers=headers,
                data=f,
                timeout=120,
            )
        if r.ok:
            url = r.json().get("browser_download_url", "")
            if get_verbose():
                info(f"Podcast: audio uploaded → {url}")
            return url
        if get_verbose():
            warning(f"Podcast: MP3 upload failed {r.status_code}")
        return ""

    def _update_rss(self, title: str, description: str, audio_url: str, mp3_path: str) -> None:
        file_size = os.path.getsize(mp3_path) if os.path.exists(mp3_path) else 0
        pub_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        guid = f"ep-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        feed_url = f"https://{self._owner}.github.io/{self._repo_name}/podcast/feed.xml"

        new_item = (
            f"\n    <item>"
            f"\n      <title><![CDATA[{title}]]></title>"
            f"\n      <description><![CDATA[{description}]]></description>"
            f"\n      <enclosure url=\"{audio_url}\" length=\"{file_size}\" type=\"audio/mpeg\"/>"
            f"\n      <guid>{guid}</guid>"
            f"\n      <pubDate>{pub_date}</pubDate>"
            f"\n    </item>"
        )

        os.makedirs(os.path.join(ROOT_DIR, "podcast"), exist_ok=True)

        if os.path.exists(self.RSS_PATH):
            with open(self.RSS_PATH, "r", encoding="utf-8") as f:
                rss = f.read()
            rss = rss.replace("</channel>", f"{new_item}\n  </channel>")
        else:
            rss = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n'
                '  <channel>\n'
                '    <title>Dark Wisdom Podcast</title>\n'
                '    <description>Deep psychology, Jungian philosophy, and uncomfortable truths about the human mind.</description>\n'
                f'    <link>https://{self._owner}.github.io/{self._repo_name}</link>\n'
                '    <language>en</language>\n'
                '    <itunes:category text="Self-Improvement"/>\n'
                '    <itunes:explicit>no</itunes:explicit>'
                f'{new_item}\n'
                '  </channel>\n'
                '</rss>'
            )

        with open(self.RSS_PATH, "w", encoding="utf-8") as f:
            f.write(rss)

        if get_verbose():
            info(f"Podcast: RSS updated. One-time: submit to Spotify → {feed_url}")

    def _push_rss(self) -> None:
        """Commit and push podcast/feed.xml."""
        cwd = ROOT_DIR
        subprocess.run(["git", "config", "user.email", "ci@moneyprinter.io"], cwd=cwd)
        subprocess.run(["git", "config", "user.name", "MoneyPrinterCI"], cwd=cwd)
        subprocess.run(["git", "add", "podcast/feed.xml"], cwd=cwd)
        result = subprocess.run(
            ["git", "commit", "-m", "chore: add podcast episode [skip ci]"],
            cwd=cwd, capture_output=True,
        )
        if result.returncode == 0:
            subprocess.run(["git", "push"], cwd=cwd)
            if get_verbose():
                success("Podcast: RSS pushed to repo.")

    def add_episode(self, title: str, script: str, wav_path: str) -> str:
        """Full pipeline: WAV → MP3 → GitHub Release → RSS update → push. Returns audio URL."""
        if not self.token or not self.repo:
            if get_verbose():
                warning("Podcast: GITHUB_TOKEN or GITHUB_REPOSITORY not set — skipping.")
            return ""

        mp3_path = self._to_mp3(wav_path)
        if not mp3_path:
            return ""

        tag = f"podcast-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        release = self._create_github_release(tag, title)
        if not release:
            return ""

        audio_url = self._upload_mp3(release["upload_url"], mp3_path)
        if not audio_url:
            return ""

        self._update_rss(title, script[:500], audio_url, mp3_path)
        self._push_rss()

        return audio_url
