"""Cache a modest set of Wikidata CC0 query results for reproducible facts."""
import hashlib
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/russia/sources'
HEADERS = {'User-Agent': 'TinyRU-EducationalFacts/1.0 (local research; Wikidata CC0)',
           'Accept': 'application/sparql-results+json'}
PREFIX = '''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
'''
QUERIES = {
 'regions': '''SELECT DISTINCT ?item ?itemLabel ?value ?valueLabel WHERE {
 wd:Q159 wdt:P150 ?item. ?item wdt:P36 ?value.
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY ?item''',
 'cities': '''SELECT DISTINCT ?item ?itemLabel ?year ?river ?riverLabel WHERE {
 { SELECT ?item WHERE { ?item wdt:P31 wd:Q7930989; wdt:P17 wd:Q159. }
 ORDER BY xsd:integer(STRAFTER(STR(?item), "entity/Q")) LIMIT 650 }
 OPTIONAL { ?item wdt:P571 ?year. }
 OPTIONAL { ?item wdt:P206 ?river. }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY ?item''',
 'rivers': '''SELECT DISTINCT ?item ?itemLabel ?value ?valueLabel WHERE {
 { SELECT ?item ?value WHERE { ?item wdt:P31 wd:Q4022; wdt:P17 wd:Q159; wdt:P403 ?value. }
 ORDER BY xsd:integer(STRAFTER(STR(?item), "entity/Q")) LIMIT 250 }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY ?item''',
 'people': '''SELECT DISTINCT ?item ?itemLabel ?birth ?death ?place ?placeLabel WHERE {
 VALUES ?occupation { wd:Q49757 wd:Q4964182 wd:Q36834 wd:Q483501 wd:Q901 wd:Q170790 }
 ?item wdt:P31 wd:Q5; wdt:P106 ?occupation; wdt:P27 ?country.
 VALUES ?country { wd:Q159 wd:Q15180 wd:Q34266 }
 ?item wdt:P569 ?birth; wdt:P19 ?place; wikibase:sitelinks ?links.
 ?place wdt:P17 wd:Q159.
 FILTER(?links >= 25)
 OPTIONAL { ?item wdt:P570 ?death. }
 OPTIONAL { ?item wdt:P19 ?place. }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY DESC(?links) ?item LIMIT 800''',
 'books': '''SELECT DISTINCT ?item ?itemLabel ?value ?valueLabel ?year WHERE {
 { SELECT DISTINCT ?item ?value WHERE {
 ?item wdt:P50 ?value; wdt:P407 wd:Q7737; wikibase:sitelinks ?links.
 FILTER(?links >= 8)
 ?value wdt:P27 ?country.
 VALUES ?country { wd:Q159 wd:Q15180 wd:Q34266 }
 ?item wdt:P31/wdt:P279* wd:Q47461344.
 } ORDER BY DESC(?links) ?item LIMIT 450 }
 OPTIONAL { ?item wdt:P577 ?year. }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY ?item''',
 'museums': '''SELECT DISTINCT ?item ?itemLabel ?place ?placeLabel ?year WHERE {
 { SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q33506; wdt:P17 wd:Q159. }
 ORDER BY xsd:integer(STRAFTER(STR(?item), "entity/Q")) LIMIT 200 }
 OPTIONAL { ?item wdt:P131 ?place. }
 OPTIONAL { ?item wdt:P571 ?year. }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru". }
 } ORDER BY ?item''',
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, body in QUERIES.items():
        query = PREFIX+body
        (OUT/(name+'.rq')).write_text(query, encoding='utf-8')
        target = OUT/(name+'.json')
        if not target.exists():
            url = 'https://query-next.wikidata.org/sparql?'+urllib.parse.urlencode(dict(query=query, format='json'))
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as response:
                        data = response.read()
                    assert 'results' in json.loads(data)
                    target.write_bytes(data)
                    break
                except Exception as exc:
                    print(name, type(exc).__name__, str(exc), flush=True)
                    if attempt:
                        break
                    # WDQS is temporarily limited to one request per minute.
                    # Honor that limit rather than retrying immediately.
                    delay = max(65, int(exc.headers.get('Retry-After', '65'))) if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else 5
                    time.sleep(delay)
            time.sleep(3)
        if target.exists():
            count = len(json.loads(target.read_text(encoding='utf-8-sig'))['results']['bindings'])
            manifest[name] = dict(rows=count, sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                                  source='https://query-next.wikidata.org/', license='CC0-1.0',
                                  retrieved='2026-11-24')
            print(name, count, flush=True)
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
