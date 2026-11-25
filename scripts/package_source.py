"""Archive the reviewable project, excluding tools, caches and temporary runs."""
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'dist/tiny-ru-source.zip'
roots=['training','dos','windows','data','scripts','tests','docs','reports','experiments']
files=[ROOT/name for name in ['README.md','MODEL_CARD.md','LICENSE','UPSTREAM.md','DATA_LICENSES.md','PUBLICATION.json','requirements.txt','requirements-report.txt','.gitignore','.gitattributes']]
for dirname in roots:
    for p in (ROOT/dirname).rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        if p.suffix.lower() in ('.o','.obj','.map','.pdb','.pyc','.tmp'):continue
        if p.suffix=='.pt' and p.name!='release.pt' and p not in (ROOT/'experiments/v2-release/baseline.pt',ROOT/'experiments/r2-release/baseline.pt'):continue
        if p.name=='TINY387.EXE':continue
        files.append(p)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(files):
        info=zipfile.ZipInfo(str(p.relative_to(ROOT)).replace('\\','/'),date_time=(2026,11,25,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,p.read_bytes())
print(out,out.stat().st_size)
