"""UTF-8 terminal bridge to CP866 native/DOS redirected byte streams."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from tokenizer import normalize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('executable',type=Path)
    p.add_argument('--cwd',type=Path,default=ROOT/'dos')
    args=p.parse_args()
    # Run one line per subprocess so output is immediate on any host console.
    for line in sys.stdin:
        line=normalize(line).rstrip('\r\n')
        if line.strip() in ('quit','exit'):break
        result=subprocess.run([str(args.executable.resolve()),'/P','0'],cwd=args.cwd,input=(line+'\nquit\n').encode('cp866',errors='replace'),stdout=subprocess.PIPE)
        sys.stdout.write(result.stdout.decode('cp866'))
        sys.stdout.flush()
        if result.returncode:sys.exit(result.returncode)


if __name__=='__main__':main()
