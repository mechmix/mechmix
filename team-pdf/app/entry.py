"""Double-click entry point: prepare and check the runtime before opening UI."""
import argparse
import json
import pathlib
import sys
import traceback
from portable_runtime import APP_ROOT,cache_root,engine_directory

def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--test-output');p.add_argument('--no-browser',action='store_true');args=p.parse_args()
    engine_directory()
    manifest=json.loads((APP_ROOT/'office-manifest.json').read_text())
    marker=cache_root()/('verified-'+manifest['sha256'][:12]+'-v2.2.txt')
    if args.self_test or not marker.exists():
        print('Checking VSD, VSDX, SOR, TRC and BDR conversion...',flush=True)
        from self_test import run
        run(args.test_output)
        marker.write_text('All bundled format checks passed.\n')
    if args.self_test:return 0
    from server import main as serve
    serve(launch_browser=not args.no_browser)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:sys.exit(0)
    except Exception as error:
        from engine_support import record
        record(traceback.format_exc());print('Could not start: '+str(error),flush=True);sys.exit(1)
