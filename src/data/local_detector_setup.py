"""Explicit compact torchvision weight download; never called by application startup."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

URL='https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth'


def download(destination):
    path=Path(destination)
    if path.exists():raise FileExistsError('Destination exists; refusing to overwrite model assets.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.download')
    size=0
    try:
        with urlopen(Request(URL,headers={'User-Agent':'adaptive-memory-research/1.0'}),timeout=60) as response, temporary.open('xb') as stream:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>16*1024*1024:raise ValueError('Unexpected model size; download stopped.')
                stream.write(chunk)
        digest=hashlib.sha256(temporary.read_bytes()).hexdigest()
        if not digest.startswith('a79551df'):raise ValueError('Official weight hash does not match; file not accepted.')
        # Hard-link publication is atomic and refuses an existing destination.
        import os
        os.link(temporary,path)
        return {'url':URL,'bytes':size,'sha256':digest,'destination':str(path)}
    finally:temporary.unlink(missing_ok=True)


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',default='models/local/ssdlite320.pt')
    args=parser.parse_args()
    print(json.dumps(download(args.out),indent=2))
