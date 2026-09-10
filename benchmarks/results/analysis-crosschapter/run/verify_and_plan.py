from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parent
src=Path('/Users/cuining/Documents/GitHub/story-skill/benchmarks/analysis-crosschapter/source.txt')
index=Path('/Users/cuining/Documents/GitHub/story-skill/benchmarks/analysis-crosschapter/chapters.json')
txt=src.read_text()
chapters=json.loads(index.read_text())
chunks=[]
for f in sorted((r/'logs').glob('*.stdout.txt')):
 try: d=json.loads(f.read_text())
 except (ValueError,UnicodeError): continue
 if isinstance(d,dict) and 'chunks' in d: chunks.extend(d['chunks'])
chunks=list({x['ordinal']:x for x in chunks}.values()); chunks.sort(key=lambda x:x['ordinal'])
checks={'source_characters':len(txt),'source_file_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'chapters_count':len(chapters),'chunks_count':len(chunks),'all_chunk_text_exact':''.join(x['text'] for x in chunks)==txt,'contiguous':chunks[0]['start']==0 and chunks[-1]['end']==len(txt) and all(a['end']==b['start'] for a,b in zip(chunks,chunks[1:])),'chapter_checks':[]}
for c in chapters:
 cs=[x for x in chunks if x['start']>=c['start'] and x['end']<=c['end']]
 checks['chapter_checks'].append({'title':c['title'],'start':c['start'],'end':c['end'],'title_matches':txt[c['start']:].startswith(c['title']),'chunks':[x['ordinal'] for x in cs],'exact_coverage':bool(cs) and cs[0]['start']==c['start'] and cs[-1]['end']==c['end'] and all(x['title']==c['title'] for x in cs)})
assert checks['all_chunk_text_exact'] and checks['contiguous'] and all(c['title_matches'] and c['exact_coverage'] for c in checks['chapter_checks'])
(r/'coverage_review.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
queries=[
('姓氏资格和旁观认可','『你怎麽會姓趙','所以我終於不知道阿Q究竟什麽姓。',0),
('考据限度与先告死讯','他活着的時候','然而也再沒有別的方法了。',0),
('精神胜利受到损失挑战','很白很亮的一堆洋錢','他睡着了。',0),
('受打反获尊敬的竞争解释','說也奇怪','阿Q此後倒得意了許多年。',3991),
('观看鼓励施暴','酒店裏的人大笑了','酒店裏的人也九分得意的笑。',3991),
('欲望的后代名义','『斷子絕孫的阿Q！』','卽此一端，我們便可以知道女人是害人的東西。',6266),
('处罚转为财物并延续寒冷','如是云云的教訓了一通','雖然不比赤膊之有切膚之痛',8660),
('对抗小D没有恢复饭碗','這一場『龍虎鬭』','於是他決計出門求食去了。',8985),
('中兴身份再被后续揭示修正','只有一班閒人們','這實在是『斯亦不足畏也矣』。',13634),
('革命让称呼反转','『老Q』','趙白眼回家，便從腰間扯下搭連來',14028),
('革命梦想重复旧支配','『這時未莊的一夥鳥男女','他也仍然肚餓',14028),
('不准他人和自己受限并非平等','小D也將辮子盤在頭頂上了','他除卻趕緊去和假洋鬼子商量之外，再沒有別的道路了。',16546),
('熟悉棍棒与失意后的幻想','『唔，……這個……』','思想裏纔又出現白盔白甲的碎片。',16546),
('抢案限知与问讯预设','『我本來要……來投……』','然而老頭子使了一個眼色',19148),
('圆圈安慰及示众动机','阿Q正羞愧自己畫得不圓','但幸而第二天倒也沒有辭。',19148),
('表演动作受限到求救与死后舆论','他省悟了，這是繞到法場去的路','他們白跟一趟了。',19148)
]
plan=[]
for n,(why,a,b,lo) in enumerate(queries,1):
 start=txt.index(a,lo); end=txt.index(b,start)+len(b)
 plan.append({'id':n,'purpose':why,'start':start,'end':end,'chunk_ids':[x['ordinal'] for x in chunks if x['start']<end and x['end']>start]})
(r/'inputs/reread-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
print(json.dumps({'coverage':checks,'reread_plan':plan},ensure_ascii=False,indent=2))
