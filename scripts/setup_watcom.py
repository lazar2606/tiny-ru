"""Extract a downloaded official Open Watcom self-extracting ZIP, Linux host."""
import os
import sys
import zipfile
from pathlib import Path

archive=Path(sys.argv[1])
destination=Path(sys.argv[2])
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        if name.startswith(('binl64/','binl/','h/','lib286/')) or name in ('license.txt',):
            z.extract(name,destination)
for dirname in ('binl64','binl'):
    for path in (destination/dirname).glob('*'):
        if path.is_file():path.chmod(0o755)
print(destination)
