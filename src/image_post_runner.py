"""
Entry point for the spiritual image post pipeline.
Called by .github/workflows/image_post_cron.yml every 6 hours.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from classes.ImagePost import ImagePost

if __name__ == "__main__":
    ImagePost().run()
