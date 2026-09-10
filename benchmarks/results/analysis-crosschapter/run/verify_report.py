from pathlib import Path
import json,re,hashlib
r=Path(__file__).resolve().parent
source=Path('/Users/cuining/Documents/GitHub/story-skill/benchmarks/analysis-crosschapter/source.txt')
txt=source.read_text(); report=(r/'report_submission.md').read_text()
body=''.join(line for line in report.splitlines() if not line.startswith('#'))
count=len(re.sub(r'\s','',body))
quotes=re.findall('『([^『』]+)』',report)
results={'body_characters_no_whitespace':count,'length_range':[1800,2400],'length_pass':1800<=count<=2400,'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'quotes':[{'quote':q,'exact_in_source':q in txt} for q in quotes],'chunks':[]}
for n in range(1,15):
 d=json.loads((r/f'inputs/chunk-{n:02d}.json').read_text())
 results['chunks'].append({'chunk':n,'findings':len(d['findings']),'all_quotes_exact':all(x['quote'] in txt for x in d['findings'])})
assert results['length_pass'] and all(x['exact_in_source'] for x in results['quotes']) and all(x['all_quotes_exact'] for x in results['chunks'])
(r/'report_validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
