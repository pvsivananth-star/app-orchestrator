import sys
print("DEBUG: __main__ loaded", file=sys.stderr)
from .cli import run
if __name__ == "__main__":
    print("DEBUG: calling run()", file=sys.stderr)
    run()
