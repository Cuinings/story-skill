from pathlib import Path
import datetime
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
state_path = ROOT / 'process.json'
state = json.loads(state_path.read_text())
number = len(state['actions']) + 1
argv = sys.argv[1:]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(argv, capture_output=True)
stem = f'command-{number:03d}'
(ROOT / (stem + '.stdout')).write_bytes(result.stdout)
(ROOT / (stem + '.stderr')).write_bytes(result.stderr)
meta = {'argv': argv, 'cwd': str(ROOT), 'started_utc': started,
        'exit_code': result.returncode, 'stdout': stem + '.stdout',
        'stderr': stem + '.stderr'}
(ROOT / (stem + '.json')).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
state['actions'].append(meta)
for marker in ('--file', '--input'):
    if marker in argv:
        resource = argv[argv.index(marker) + 1]
        if resource not in state['resources_read']:
            state['resources_read'].append(resource)
if any(arg.endswith('/story.py') for arg in argv):
    runtime = next(arg for arg in argv if arg.endswith('/story.py'))
    state.setdefault('executed_runtime', runtime)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
