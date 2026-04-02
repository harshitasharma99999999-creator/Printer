"""
Entry point for the 24/7 free dropshipping automation.
Called by .github/workflows/dropshipping_cron.yml
"""
import sys
import os

# Add src/ to path (same pattern as cron.py / webapp_runner.py)
sys.path.insert(0, os.path.dirname(__file__))

from classes.Dropshipping import Dropshipping

if __name__ == "__main__":
    bot = Dropshipping()
    bot.run()
