import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from core import Store, Engine
from build_release import validate_config, render, ROOT
import xml.etree.ElementTree as ET


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'db.sqlite3'
        self.s=Store(self.path)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda:self.s.db.close())

    def test_clean_install_and_existing_data_preserved(self):
        self.assertEqual(self.s.categories(),[])
        self.assertEqual(self.s.tasks(),[])
        self.assertEqual(self.s.rows('1970-01-01','2099-12-31'),[])
        self.s.add_category('Kendi başlığım')
        tid=self.s.save_task('Kendi görevim',self.s.categories()[0]['id'],30)
        self.s.db.close(); self.s=Store(self.path)
        self.assertEqual(self.s.task(tid)['title'],'Kendi görevim')
        self.assertEqual(len(self.s.categories()),1)

    def test_missing_category_is_actionable(self):
        with self.assertRaisesRegex(ValueError,'ana başlık'):
            self.s.save_task('Görev',None,30)

    def setup_engine(self):
        self.s.add_category('Test')
        self.task=self.s.task(self.s.save_task('Görev',self.s.categories()[0]['id'],1))
        self.now=0
        self.base=datetime(2026,9,20,23,58)
        self.e=Engine(self.s,lambda:self.now,lambda:self.base+timedelta(seconds=self.now))
        self.e.start_work(self.task)

    def test_overtime_after_midnight_does_not_recount_task(self):
        self.setup_engine(); self.now=60; self.e.tick()
        self.assertEqual(self.s.task(self.task['id'])['rounds'],1)
        self.now=120; self.s.ensure_task_day(self.base+timedelta(seconds=self.now))
        self.e.continue_work(); self.now=180; self.e.tick(); self.e.finish()
        self.assertEqual(self.s.task(self.task['id'])['rounds'],0)
        rows=self.s.rows('1970-01-01','2099-12-31')
        self.assertEqual(len(rows),1); self.assertEqual(rows[0]['seconds'],120)
        self.assertEqual(self.s.daily('2026-09-21','2026-09-21')[0]['seconds'],60)

    def test_restart_write_failure_preserves_active_work(self):
        self.setup_engine(); self.now=20; self.e.tick()
        old_id=self.e.work['id']
        self.s.db.execute("CREATE TRIGGER refuse BEFORE INSERT ON settings BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.e.restart()
        self.assertEqual(self.e.work['id'],old_id)
        self.assertEqual(self.s.get('active_v2')['work']['id'],old_id)
        self.s.db.execute('DROP TRIGGER refuse')
        self.e.finish()
        self.assertEqual(len(self.s.rows('1970-01-01','2099-12-31')),1)

    def test_late_tick_uses_actual_deadline_for_daily_task_rounds(self):
        self.setup_engine()  # 23:58 + 1 minute = previous day's 23:59
        self.now=600
        self.s.ensure_task_day(self.base+timedelta(seconds=self.now))
        self.e.tick()
        row=self.s.rows('1970-01-01','2099-12-31')[0]
        self.assertEqual(row['finished_at'],'2026-09-20T23:59:00')
        self.assertEqual(self.s.task(self.task['id'])['rounds'],0)

    def test_store_identity_is_required_and_manifest_escapes_text(self):
        with self.assertRaises(ValueError):validate_config({})
        config=dict(IdentityName='Test.Odak',Publisher='CN=Test & Company',
          PublisherDisplayName='Test & Company',DisplayName='Test <Odak>',
          SupportEmail='support@example.org',PrivacyUrl='https://example.org/privacy',Version='2.2.0.0')
        template=(ROOT/'store'/'AppxManifest.template.xml').read_text(encoding='utf-8')
        manifest=render(template,validate_config(config),xml=True)
        tree=ET.fromstring(manifest); ns={'f':'http://schemas.microsoft.com/appx/manifest/foundation/windows10'}
        self.assertEqual(tree.find('f:Identity',ns).get('Publisher'),'CN=Test & Company')
        self.assertEqual(tree.find('f:Properties/f:DisplayName',ns).text,'Test <Odak>')
        self.assertNotIn('{{',manifest)
        self.assertIn('runFullTrust',manifest)
        for invalid in ('0.2.0.0','2.2.0.1','2.65536.0.0','2.2'):
            with self.assertRaises(ValueError):validate_config(dict(config,Version=invalid))

if __name__=='__main__':unittest.main()
