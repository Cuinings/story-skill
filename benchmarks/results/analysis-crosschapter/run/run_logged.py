from pathlib import Path
import sys, subprocess, json, datetime, shlex
root=Path(__file__).resolve().parent
p=root/'process.json'
state=json.loads(p.read_text())
argv=sys.argv[1:]
n=len(state['commands'])
prefix=f"logs/{n:03d}"
r=subprocess.run(argv,capture_output=True)
(root/(prefix+'.stdout.txt')).write_bytes(r.stdout)
(root/(prefix+'.stderr.txt')).write_bytes(r.stderr)
entry={'sequence':n,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'argv':argv,'command':shlex.join(argv),'exit_code':r.returncode,'stdout':prefix+'.stdout.txt','stderr':prefix+'.stderr.txt'}
state['commands'].append(entry)
if r.returncode: state['failures'].append(entry)
p.write_text(json.dumps(state,ensure_ascii=False,indent=2))
sys.stdout.buffer.write(r.stdout)
sys.stderr.buffer.write(r.stderr)
sys.exit(r.returncode)
