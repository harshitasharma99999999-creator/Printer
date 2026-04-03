import os
import requests

from config import get_verbose
from status import warning, success


class Hashnode:
    """
    Hashnode GraphQL API — publishes articles to your Hashnode blog.
    Free. Hashnode articles rank on Google and build long-term SEO traffic.
    """

    GQL_URL = "https://gql.hashnode.com"

    def __init__(self):
        self.token = os.environ.get("HASHNODE_ACCESS_TOKEN", "").strip()
        self.publication_id = os.environ.get("HASHNODE_PUBLICATION_ID", "").strip()

    def post_article(self, title: str, content_markdown: str, tags: list = None) -> str:
        """Publish article to Hashnode. Returns URL."""
        if not self.token or not self.publication_id:
            if get_verbose():
                warning("Hashnode: HASHNODE_ACCESS_TOKEN or HASHNODE_PUBLICATION_ID not set — skipping.")
            return ""

        default_tags = [
            {"name": "Psychology", "slug": "psychology"},
            {"name": "Self Improvement", "slug": "self-improvement"},
            {"name": "Philosophy", "slug": "philosophy"},
            {"name": "Mindset", "slug": "mindset"},
        ]

        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) {
            post {
              id
              url
              title
            }
          }
        }
        """

        try:
            r = requests.post(
                self.GQL_URL,
                headers={
                    "Authorization": self.token,
                    "Content-Type": "application/json",
                },
                json={
                    "query": mutation,
                    "variables": {
                        "input": {
                            "title": title,
                            "contentMarkdown": content_markdown,
                            "publicationId": self.publication_id,
                            "tags": tags or default_tags,
                        }
                    },
                },
                timeout=30,
            )

            data = r.json()
            if "errors" in data:
                if get_verbose():
                    warning(f"Hashnode: post failed: {data['errors']}")
                return ""

            url = (
                data.get("data", {})
                .get("publishPost", {})
                .get("post", {})
                .get("url", "")
            )
            if url and get_verbose():
                success(f"Hashnode: article published → {url}")
            return url

        except Exception as e:
            if get_verbose():
                warning(f"Hashnode: {e}")
            return ""
