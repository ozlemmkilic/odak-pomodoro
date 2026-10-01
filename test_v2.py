import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from core import Store,Engine,record,allocate

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'odak.sqlite3'; self.store=Store(self.path); self.now=0
        self.store.add_category('Test kategorisi')
        self.cat=self.store.categories()[0]['id']; self.tid=self.store.save_task('Tenses',self.cat,1)
        self.task=self.store.task(self.tid); self.engine=Engine(self.store,lambda:self.now,lambda:datetime(2026,9,20,23,59,30)+timedelta(seconds=self.now))
    def tearDown(self):self.store.db.close(); self.temp.cleanup()
    def jump(self,n):self.now+=n; return self.engine.tick()
    def test_focus_auto_break_and_no_auto_work(self):
        self.engine.start_work(self.task); self.assertEqual(self.jump(60),'work_done')
        self.assertEqual(self.engine.mode,'short'); self.assertIsNotNone(self.engine.timer.anchor)
        rows=self.store.rows('2026-09-20','2026-09-21'); self.assertEqual(len(rows),1); self.assertEqual(rows[0]['seconds'],60)
        self.assertEqual(self.store.task(self.tid)['rounds'],1); self.assertFalse(self.store.task(self.tid)['done'])
        self.assertEqual(self.jump(300),'break_done'); self.assertIsNone(self.engine.timer)
        self.assertEqual(len(self.store.rows('2026-09-20','2026-09-21')),1)
        self.assertEqual([r['seconds'] for r in self.store.daily('2026-09-20','2026-09-21')],[30,30])
    def test_long_break_schedule_and_auto_off(self):
        self.store.set('long_every',2); self.store.set('auto_break',False)
        for i in range(2):
            self.engine.start_work(self.task); self.jump(60)
            self.assertIsNone(self.engine.timer.anchor)
            self.assertEqual(self.engine.mode,'short' if i==0 else 'long')
            self.assertEqual(self.engine.timer.total,300 if i==0 else 900)
            self.engine.cancel()
    def test_pause_does_not_count_and_partial_does_not_start_break(self):
        self.engine.start_work(self.task); self.jump(15); self.engine.pause_resume(); self.jump(90)
        self.assertEqual(self.engine.timer.elapsed,15); self.engine.pause_resume(); self.jump(10)
        self.assertEqual(self.engine.finish(),'saved'); self.assertIsNone(self.engine.timer)
        r=self.store.rows('2026-09-20','2026-09-21')[0]; self.assertEqual(r['seconds'],25); self.assertEqual(r['status'],'Erken bitirildi')
        self.assertEqual(self.store.task(self.tid)['rounds'],1)
    def test_recover_work_paused_and_recover_break(self):
        self.engine.start_work(self.task); self.jump(20); self.engine.close()
        other=Engine(self.store,lambda:self.now); self.assertEqual(other.timer.elapsed,20); self.assertIsNone(other.timer.anchor)
        self.jump(40)  # closed engine is paused
        self.assertEqual(self.engine.timer.elapsed,20)
        self.engine.pause_resume(); self.jump(40); self.engine.close()
        other=Engine(self.store,lambda:self.now); self.assertEqual(other.mode,'short'); self.assertIsNone(other.timer.anchor)
    def test_old_data_migrates_with_backup_and_old_active_recovers(self):
        r=record('Eski kayıt',self.cat,datetime(2026,9,19,12),30); r['seconds']=1800; allocate(r['days'],datetime(2026,9,19,12,30),1800); self.store.save(r)
        active=record('Yarım kalan',self.cat,datetime(2026,9,20,12),25); active['seconds']=60; active['days']={'2026-09-20':60}; self.store.set('active',active)
        self.store.db.executescript('DROP TABLE session_tasks; DROP TABLE tasks;'); self.store.db.close(); self.store=Store(self.path)
        self.assertEqual(len(list(self.path.parent.glob('*.v1-backup-*'))),1)
        self.assertEqual(self.store.rows('2026-09-19','2026-09-19')[0]['seconds'],1800)
        other=Engine(self.store); self.assertEqual(other.work['title'],'Yarım kalan'); self.assertEqual(other.timer.elapsed,60); self.assertIsNone(other.timer.anchor)
    def test_tasks_persist_edit_done_archive_keeps_history(self):
        self.engine.start_work(self.task); self.jump(60); self.engine.cancel()
        self.store.save_task('Yeni ad',self.cat,45,self.tid); self.store.update_task(self.tid,done=True)
        self.store.db.close(); self.store=Store(self.path)
        t=self.store.task(self.tid); self.assertEqual(t['title'],'Yeni ad'); self.assertEqual(t['minutes'],45); self.assertTrue(t['done'])
        self.store.update_task(self.tid,archived=True); self.assertIsNone(self.store.task(self.tid))
        r=self.store.rows('2026-09-20','2026-09-21')[0]; self.assertEqual(r['title'],'Tenses')
    def test_completion_is_atomic_on_failure(self):
        self.engine.start_work(self.task)
        self.store.db.execute("CREATE TRIGGER refuse BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.jump(60)
        self.assertEqual(self.engine.mode,'work'); self.assertEqual(self.engine.cycles,0)
        self.store.db.execute('DROP TRIGGER refuse'); self.engine.tick(); self.engine.tick()
        self.assertEqual(len(self.store.rows('2026-09-20','2026-09-21')),1); self.assertEqual(self.engine.cycles,1)
    def test_delayed_tick_assigns_time_before_deadline(self):
        self.engine.start_work(self.task); self.jump(3600)
        self.assertEqual([r['seconds'] for r in self.store.daily('2026-09-20','2026-09-21')],[30,30])

if __name__=='__main__':unittest.main()
