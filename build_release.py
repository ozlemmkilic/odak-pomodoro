"""Build an offline Windows x64 app and optionally an unsigned Store MSIX.
No uploads, certificate installation, system settings changes or user DB reads.
"""
import argparse
import hashlib
import html
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VERSION='2.2.0.0'
REBUILD_FILES=('app.py','modern.py','core.py','alarm.wav','check.svg',
 'GIZLILIK.txt','THIRD_PARTY_NOTICES.txt','requirements.txt','requirements-build.txt',
 'build_release.py','BENI_OKU.txt','EXE_OLUSTUR.bat','BASLAT.bat')

def validate_config(c):
    keys=('IdentityName','Publisher','PublisherDisplayName','DisplayName','SupportEmail','PrivacyUrl','Version')
    for key in keys:
        if not isinstance(c.get(key),str) or not c[key].strip():raise ValueError(f'{key} alanı boş olamaz.')
        c[key]=c[key].strip()
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}',c['IdentityName']):raise ValueError('IdentityName Partner Center’dan aynen kopyalanmalı.')
    if not c['Publisher'].startswith('CN='):raise ValueError('Publisher değeri CN= ile başlamalı.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',c['SupportEmail']):raise ValueError('Geçerli bir genel destek e-postası gir.')
    if not c['PrivacyUrl'].startswith('https://') or any(x in c['PrivacyUrl'] for x in (' ', '<','>')):raise ValueError('Yayımlanmış HTTPS gizlilik adresini gir.')
    if not re.fullmatch(r'\d+\.\d+\.\d+\.0',c['Version']):raise ValueError('Sürüm dört parçalı ve son parçası 0 olmalı.')
    parts=[int(x) for x in c['Version'].split('.')]
    if parts[0]<1 or max(parts)>65535:raise ValueError('Geçersiz sürüm aralığı.')
    return c

def render(template,config,xml=False):
    def replace(m):
        value=config[m.group(1)]
        return html.escape(value,quote=True) if xml else value
    result=re.sub(r'\{\{(\w+)\}\}',replace,template)
    if xml:ET.fromstring(result)
    return result

def read_config(interactive=False):
    path=ROOT/'store'/'store-config.json'
    if path.exists():return validate_config(json.loads(path.read_text(encoding='utf-8-sig')))
    if not interactive:raise ValueError('store/store-config.example.json dosyasını store-config.json adıyla kopyala ve doldur.')
    print('Partner Center > Product management > Product identity bilgilerini kullan.')
    c={}
    for key in ('IdentityName','Publisher','PublisherDisplayName','DisplayName','SupportEmail','PrivacyUrl'):
        c[key]=input(f'{key}: ').strip()
    c['Version']=VERSION; validate_config(c)
    path.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
    return c

def makeappx_path():
    path=shutil.which('makeappx.exe')
    if path:return Path(path)
    root=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Windows Kits'/'10'/'bin'
    candidates=list(root.glob('10.*.*/x64/makeappx.exe'))
    if not candidates:raise ValueError('Windows SDK kurulamadı/bulunamadı. Windows SDK içindeki MSIX Packaging Tools bileşenini kur.')
    return max(candidates,key=lambda p:tuple(int(x) for x in p.parent.parent.name.split('.')))

def run(args,**kwargs):
    subprocess.run([str(a) for a in args],check=True,cwd=ROOT,**kwargs)

def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--msix',action='store_true'); p.add_argument('--interactive',action='store_true')
    args=p.parse_args()
    if sys.platform!='win32' or struct.calcsize('P')!=8 or platform.machine().lower() not in ('amd64','x86_64'):
        raise ValueError('Bu derleme Windows x64 üzerinde 64 bit x64 Python gerektirir.')
    c=read_config(args.interactive) if args.msix else None
    sdk=makeappx_path() if args.msix else None
    version=c['Version'] if c else VERSION
    destination=ROOT/'release'/f'{version}-{"store" if args.msix else "portable"}'
    if destination.exists():raise ValueError(f'Çıktı zaten var: {destination}\nEski çıktıyı başka bir klasöre taşı veya sürümü artır.')
    # Source archive retention and notices are part of the LGPL distribution workflow.
    run([sys.executable,ROOT/'store'/'prepare_sources.py'])
    run([sys.executable,'-m','unittest','discover','-s',ROOT,'-v'])
    with tempfile.TemporaryDirectory(prefix='odak-release-') as td:
        temp=Path(td); resources=temp/'resources'; resources.mkdir()
        for name in ('alarm.wav','check.svg','GIZLILIK.txt','THIRD_PARTY_NOTICES.txt'):
            shutil.copy2(ROOT/name,resources/name)
        shutil.copytree(ROOT/'LICENSES',resources/'LICENSES')
        # Python's Windows distribution provides its license with the interpreter.
        python_license=Path(sys.base_prefix)/'LICENSE.txt'
        if not python_license.is_file():raise ValueError('Python LICENSE.txt bulunamadı; python.org Python 3.13 x64 kullan.')
        shutil.copy2(python_license,resources/'LICENSES'/'Python-LICENSE.txt')
        import PyInstaller
        pi_license=Path(PyInstaller.__file__).parent.parent/'pyinstaller-6.22.3.dist-info'/'licenses'/'COPYING.txt'
        if not pi_license.exists():
            import importlib.metadata as metadata
            dist=metadata.distribution('pyinstaller')
            found=[dist.locate_file(f) for f in (dist.files or []) if str(f).endswith('COPYING.txt')]
            if not found:raise ValueError('PyInstaller lisans metni bulunamadı.')
            pi_license=found[0]
        shutil.copy2(pi_license,resources/'LICENSES'/'PyInstaller-COPYING.txt')
        rebuild=resources/'rebuild'; rebuild.mkdir()
        for name in REBUILD_FILES:shutil.copy2(ROOT/name,rebuild/name)
        # Never copy local store-config.json, databases, caches or personal files.
        (rebuild/'store').mkdir()
        for name in ('REBUILD.txt','prepare_sources.py','odak.ico'):
            shutil.copy2(ROOT/'store'/name,rebuild/'store'/name)
        shutil.copytree(ROOT/'store'/'Assets',rebuild/'store'/'Assets')
        if c:
            offer=render((ROOT/'store'/'SOURCE_OFFER.template.txt').read_text(encoding='utf-8'),c)
            (resources/'SOURCE_OFFER.txt').write_text(offer,encoding='utf-8')
            privacy=(resources/'GIZLILIK.txt').read_text(encoding='utf-8')+f"\nYayıncı: {c['PublisherDisplayName']}\nDestek: {c['SupportEmail']}\nGizlilik adresi: {c['PrivacyUrl']}\n"
            (resources/'GIZLILIK.txt').write_text(privacy,encoding='utf-8')
            notices=(resources/'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')+'\n\n'+offer
            (resources/'THIRD_PARTY_NOTICES.txt').write_text(notices,encoding='utf-8')
        metadata_file=temp/'version_info.txt'
        ver=tuple(int(n) for n in version.split('.'))
        display=c['DisplayName'] if c else 'Odak'
        metadata_file.write_text(f"VSVersionInfo(ffi=FixedFileInfo(filevers={ver!r}, prodvers={ver!r}, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('041F04B0', [StringStruct('FileDescription', {display!r}), StringStruct('ProductName', {display!r}), StringStruct('FileVersion', {version!r}), StringStruct('ProductVersion', {version!r}), StringStruct('OriginalFilename', 'OdakPomodoro.exe')])]), VarFileInfo([VarStruct('Translation',[1055,1200])])])",encoding='utf-8')
        run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--noupx',
          '--name','OdakPomodoro','--icon',ROOT/'store'/'odak.ico','--version-file',metadata_file,
          '--distpath',temp/'dist','--workpath',temp/'work','--specpath',temp,
          '--add-data',str(resources)+os.pathsep+'.',ROOT/'app.py'])
        app=temp/'dist'/'OdakPomodoro'
        covered={'Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll','Qt6Network.dll',
                 'Qt6OpenGL.dll','Qt6OpenGLWidgets.dll','Qt6PrintSupport.dll',
                 'Qt6Sql.dll','Qt6Xml.dll','Qt6Concurrent.dll','Qt6DBus.dll',
                 'Qt6Svg.dll','Qt6SvgWidgets.dll'}
        unexpected={p.name for p in app.rglob('Qt6*.dll')}-covered
        if unexpected:raise ValueError('Kaynak/lisans kapsamı kontrol edilmeli: '+', '.join(sorted(unexpected)))
        if c:
            shutil.copytree(ROOT/'store'/'Assets',app/'Assets')
            manifest=render((ROOT/'store'/'AppxManifest.template.xml').read_text(encoding='utf-8'),c,xml=True)
            (app/'AppxManifest.xml').write_text(manifest,encoding='utf-8')
            msix=temp/f'OdakPomodoro_{version}_x64.msix'
            run([sdk,'pack','/d',app,'/p',msix,'/h','SHA256'])
        destination.mkdir(parents=True)
        shutil.copytree(app,destination/'OdakPomodoro')
        if c:
            shutil.copy2(msix,destination/msix.name)
            run([sys.executable,ROOT/'store'/'capture_screenshots.py','--output',destination/'screenshots'])
            body=html.escape((resources/'GIZLILIK.txt').read_text(encoding='utf-8'))
            (destination/'privacy.html').write_text('<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Odak — Gizlilik</title><body style="max-width:780px;margin:48px auto;padding:24px;font:18px/1.6 system-ui;white-space:pre-wrap">'+body+'</body></html>',encoding='utf-8')
        with (destination/'build-dependencies.txt').open('w',encoding='utf-8') as dependencies:
            run([sys.executable,'-m','pip','freeze'],stdout=dependencies)
        hashes={p.relative_to(destination).as_posix():file_hash(p) for p in destination.rglob('*') if p.is_file()}
        (destination/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print(f'HAZIR: {destination}')
    print('EXE: OdakPomodoro klasörü içindeki OdakPomodoro.exe. Klasörü bütün olarak taşı.')
    if c:print('MSIX imzasız Store yükleme paketidir. Henüz yayımlanmadı. Windows testlerini ve Store rehberini tamamla.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        print(f'Derleme durdu: {e}',file=sys.stderr); sys.exit(1)
