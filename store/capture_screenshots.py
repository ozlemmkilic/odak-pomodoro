"""Capture real UI, with disposable synthetic records, never the user's DB."""
import argparse
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from modern import MainWindow
from core import record, allocate

def capture(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); app.setStyle('Fusion')
    with tempfile.TemporaryDirectory(prefix='odak-screenshots-') as temp:
        w=MainWindow(Path(temp)/'demo.sqlite3'); w.resize(1440,1200); w.show(); w.timer.stop()
        def shot(name,page=0,theme='dark'):
            w.change_page(page); w.theme_box.setCurrentIndex(1 if theme=='light' else 0); w.refresh_all()
            app.processEvents(); assert w.grab().save(str(output/name))
        shot('01-ilk-acilis.png')
        for name in ('Proje','Öğrenme','Kitap'):w.store.add_category(name)
        w.refresh_categories()
        for title,category,minutes,target in [('Taslak hazırla','Proje',30,3),('Yeni konu tekrarı','Öğrenme',25,2),('Bir bölüm oku','Kitap',20,1)]:
            tid=w.store.save_task(title,w.categories[category],minutes,target=target)
            if w.selected_id is None:w.selected_id=tid
        for ago in range(7):
            start=datetime.now().replace(hour=8,minute=0,second=0,microsecond=0)-timedelta(days=ago+1)
            for name,minutes in [('Proje',30+ago*3),('Öğrenme',25)]:
                r=record('Örnek çalışma',w.categories[name],start,minutes); r['seconds']=minutes*60
                allocate(r['days'],start+timedelta(minutes=minutes),r['seconds']); w.store.save(r)
        w.banner.hide(); w.refresh_all()
        shot('02-koyu-tema.png'); shot('03-acik-tema.png',theme='light')
        shot('04-dashboard.png',page=1)
        w.change_page(0); w.engine.start_work(w.selected_task())
        w.engine.timer.anchor-=w.engine.timer.total; w.engine.tick(); w.engine.continue_work()
        w.engine.timer.anchor-=310; w.engine.tick(); w.engine.pause_resume()
        shot('05-uzatma.png')
        w.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True)
    capture(p.parse_args().output)
