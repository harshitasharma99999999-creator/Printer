import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from classes.WebAppBuilder import WebAppBuilder
from status import error, success

if __name__ == "__main__":
    try:
        builder = WebAppBuilder()
        url = builder.run()
        success(f"WebApp deployed: {url}")
    except Exception as e:
        import traceback
        error(f"WebApp Builder failed: {e}")
        traceback.print_exc()
        sys.exit(1)
