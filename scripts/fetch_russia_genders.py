"""Cache grammatical gender metadata for the selected biographical subjects."""
import json
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
facts=[json.loads(s) for s in (ROOT/'data/russia/facts.jsonl').read_text(encoding='utf-8').splitlines()]
ids=sorted({f['subject'].rsplit('/',1)[-1] for f in facts if f['category']=='россия: биографии'})
query='PREFIX wd:<http://www.wikidata.org/entity/> PREFIX wdt:<http://www.wikidata.org/prop/direct/> SELECT ?item ?sex WHERE { VALUES ?item { '+' '.join('wd:'+i for i in ids)+' } ?item wdt:P21 ?sex. }'
path=ROOT/'data/russia/sources/genders.json'
if not path.exists():
    request=urllib.request.Request('https://query-next.wikidata.org/sparql?'+urllib.parse.urlencode(dict(query=query,format='json')),headers={'User-Agent':'TinyRU-EducationalFacts/1.0 (local research)','Accept':'application/sparql-results+json'})
    with urllib.request.urlopen(request,timeout=30) as response:path.write_bytes(response.read())
(path.with_suffix('.rq')).write_text(query,encoding='utf-8')
manifest_path=path.parent/'manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['genders']=dict(rows=len(json.loads(path.read_text(encoding='utf-8'))['results']['bindings']),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         source='https://query-next.wikidata.org/',license='CC0-1.0',retrieved='2026-11-24')
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Cached gender metadata for',len(ids),'subjects')
