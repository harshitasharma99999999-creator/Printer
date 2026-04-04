"""
Entry point for Grand Forno Cloud Kitchen Instagram automation.
Called by .github/workflows/cloudk_cron.yml — runs 3× daily.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from classes.CloudKitchen import CloudKitchen

if __name__ == "__main__":
    CloudKitchen().run()
