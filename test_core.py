import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from core import Store, Timer, allocate, record


class CoreTests(unittest.TestCase):
    def test_pause_and_completion_cap(self):
        now=[0]
        t=Timer(60,lambda:now[0]); t.resume()
        now[0]=20; t.pause()
        now[0]=200
        self.assertEqual(t.advance(),0)
        self.assertEqual(t.elapsed,20)
        t.resume(); now[0]=300; t.advance()
        self.assertEqual(t.elapsed,60)

    def test_midnight_allocation(self):
        days={}
        allocate(days,datetime(2026,9,21,0,10),1800)
        self.assertEqual(days,{'2026-09-20':1200,'2026-09-21':600})

    def test_persistence_filter_delete_and_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite3'; s=Store(p)
            s.add_category('Kategori A'); s.add_category('Kategori B')
            cats=s.categories(); a,b=cats[0]['id'],cats[1]['id']
            r=record('Tenses',a,datetime(2026,9,20,23,40),30)
            r['seconds']=1800
            allocate(r['days'],datetime(2026,9,21,0,10),1800)
            s.set('active',r); s.db.close(); s=Store(p)
            self.assertEqual(s.get('active'),r)
            s.save(r,True); s.save(r,True)
            self.assertIsNone(s.get('active'))
            self.assertEqual(len(s.rows('2026-09-20','2026-09-21')),1)
            self.assertEqual(s.rows('2026-09-20','2026-09-20')[0]['period_seconds'],1200)
            self.assertEqual(s.rows('2026-09-20','2026-09-21',b),[])
            self.assertEqual(s.daily('2026-09-21','2026-09-21',a)[0]['seconds'],600)
            with self.assertRaises(ValueError): s.add_category('Kategori A')
            s.delete(r['id'])
            self.assertEqual(s.daily('2026-09-20','2026-09-21'),[])
            s.db.close()


if __name__=='__main__':
    unittest.main()
