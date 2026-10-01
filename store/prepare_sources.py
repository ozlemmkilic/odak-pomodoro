"""Retain matching LGPL sources and notices from Qt's official HTTPS service."""
import hashlib
import json
import re
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
URLS=(
 'https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz',
 'https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtsvg-everywhere-src-6.11.2.tar.xz',
 'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz',
)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def prepare():
    cache=ROOT/'source-cache'; cache.mkdir(exist_ok=True)
    licenses=ROOT/'LICENSES'; licenses.mkdir(exist_ok=True)
    report=[]
    for url in URLS:
        name=url.rsplit('/',1)[-1]; archive=cache/name
        with urllib.request.urlopen(url+'.sha256',timeout=60) as response:
            match=re.search(r'\b[0-9a-fA-F]{64}\b',response.read().decode())
        if not match:raise ValueError('Qt SHA-256 doğrulama bilgisi bulunamadı: '+name)
        expected=match[0].lower()
        if not archive.exists() or digest(archive)!=expected:
            print('Kaynak arşivi indiriliyor: '+name,flush=True)
            temporary=archive.with_suffix('.download')
            try:
                with urllib.request.urlopen(url,timeout=60) as src,temporary.open('wb') as dest:
                    shutil.copyfileobj(src,dest)
                if digest(temporary)!=expected:raise ValueError('Kaynak arşivi SHA-256 uyuşmuyor: '+name)
                temporary.replace(archive)
            finally:temporary.unlink(missing_ok=True)
        with tarfile.open(archive,'r:xz') as tar:
            for member in tar:
                p=Path(member.name); lower=p.name.lower()
                wanted=(any(x.lower()=='licenses' for x in p.parts) or
                        lower.startswith(('license','copying','copyright','notice')) or
                        lower in ('readme.qt','qt_attribution.json'))
                if not (wanted and member.isfile() and member.size<=2_000_000):continue
                if p.is_absolute() or '..' in p.parts:raise ValueError('Geçersiz arşiv yolu')
                target=licenses/p; target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as src,target.open('wb') as dest:shutil.copyfileobj(src,dest)
        report.append({'url':url,'sha256':expected,'bytes':archive.stat().st_size})
    (cache/'SOURCE_INDEX.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    shutil.copy2(cache/'SOURCE_INDEX.json',licenses/'SOURCE_INDEX.json')
    print('Kaynaklar doğrulandı. source-cache klasörünü yayımcı olarak sakla.',flush=True)

if __name__=='__main__':prepare()
