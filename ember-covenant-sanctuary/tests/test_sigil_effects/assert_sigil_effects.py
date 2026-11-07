from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_testlib import run_topic


run_topic("sigil_effects")
