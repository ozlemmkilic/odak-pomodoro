import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta
from core import Store,Engine,planned_seconds

class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'db.sqlite3'
        self.s=Store(self.path); self.now=0; self.base=datetime(2026,9,21,12)
        self.s.add_category('Test kategorisi')
        self.tid=self.s.save_task('Modals',self.s.categories()[0]['id'],30,target=5)
        self.e=self.engine()
    def tearDown(self):self.s.db.close(); self.tmp.cleanup()
    def engine(self):return Engine(self.s,lambda:self.now,lambda:self.base+timedelta(seconds=self.now))
    def jump(self,n):self.now+=n; return self.e.tick()
    def rows(self):return self.s.rows('1970-01-01','2099-12-31')
    def test_overtime_skips_break_time_and_counts_once(self):
        self.e.start_work(self.s.task(self.tid)); self.jump(1800)
        self.assertEqual(len(self.rows()),1); self.assertEqual(self.e.cycles,1)
        self.jump(120); self.e.continue_work(); self.assertEqual(self.e.timer.elapsed,1800)
        self.jump(300); self.assertEqual(self.e.timer.elapsed,2100)
        self.e.pause_resume(); self.jump(75); self.e.pause_resume(); self.jump(300)
        self.assertEqual(self.e.finish(),'extended')
        self.assertEqual(len(self.rows()),1); self.assertEqual(self.rows()[0]['seconds'],2400)
        self.assertEqual(self.s.task(self.tid)['rounds'],1); self.assertEqual(self.e.cycles,1)
        self.assertEqual(sum(r['seconds'] for r in self.s.daily('1970-01-01','2099-12-31')),2400)
    def test_overtime_recovery_preserves_base_and_added_time(self):
        self.e.start_work(self.s.task(self.tid)); self.jump(1800); self.e.continue_work(); self.jump(245); self.e.close()
        self.e=self.engine(); self.assertEqual(self.e.mode,'overtime'); self.assertEqual(self.e.timer.elapsed,2045); self.assertIsNone(self.e.timer.anchor)
        self.e.pause_resume(); self.jump(55); self.e.finish(); self.assertEqual(self.rows()[0]['seconds'],2100)
    def test_restart_discards_short_work_and_starts_full_timer(self):
        self.e.start_work(self.s.task(self.tid)); self.jump(240); old_id=self.e.work['id']; self.e.restart()
        self.assertNotEqual(old_id,self.e.work['id']); self.assertEqual(self.e.timer.elapsed,0); self.assertEqual(self.e.timer.total,1800)
        self.assertIsNotNone(self.e.timer.anchor); self.assertEqual(len(self.rows()),0)
        self.jump(20); self.e.finish(); self.assertEqual(len(self.rows()),1); self.assertEqual(self.rows()[0]['seconds'],20)
        self.assertEqual(self.s.task(self.tid)['rounds'],1); self.assertEqual(self.e.cycles,1)
    def test_reset_overtime_keeps_original_completed_record(self):
        self.e.start_work(self.s.task(self.tid)); self.jump(1800); self.e.continue_work(); self.jump(100); self.e.restart()
        self.assertEqual(self.rows()[0]['seconds'],1800); self.assertEqual(self.e.timer.elapsed,0)
        self.assertFalse(self.e.can_continue())
    def test_daily_and_manual_reset_preserve_tasks_and_history(self):
        self.s.ensure_task_day(self.base); self.e.start_work(self.s.task(self.tid)); self.jump(20); self.e.finish()
        self.s.update_task(self.tid,done=True); self.assertEqual(self.s.task(self.tid)['rounds'],1)
        self.assertFalse(self.s.ensure_task_day(self.base))
        self.assertTrue(self.s.ensure_task_day(self.base+timedelta(days=1)))
        task=self.s.task(self.tid); self.assertFalse(task['done']); self.assertEqual(task['rounds'],0); self.assertEqual(task['target'],5)
        self.assertEqual(len(self.rows()),1)
        self.s.set('daily_reset',False); self.s.update_task(self.tid,done=True)
        self.assertFalse(self.s.ensure_task_day(self.base+timedelta(days=2))); self.assertTrue(self.s.task(self.tid)['done'])
        self.s.reset_tasks(self.base+timedelta(days=2)); self.assertFalse(self.s.task(self.tid)['done'])
    def test_target_and_estimate_include_only_between_breaks(self):
        self.assertEqual(planned_seconds(30,1),1800)
        self.assertEqual(planned_seconds(30,5,cycles=0),180*60) # 150 work + 5+5+5+15
        self.assertEqual(planned_seconds(30,2,cycles=3),75*60)
        self.assertEqual(planned_seconds(30,5,include_breaks=False),150*60)
    def test_target_preserved_on_duration_edit(self):
        self.s.save_task('Modals',self.s.categories()[0]['id'],45,self.tid)
        self.assertEqual(self.s.task(self.tid)['target'],5)
    def test_deleted_source_cannot_be_recreated_by_continue(self):
        self.e.start_work(self.s.task(self.tid)); self.jump(1800)
        self.s.delete(self.rows()[0]['id']); self.assertFalse(self.e.can_continue())
        with self.assertRaises(ValueError):self.e.continue_work()

if __name__=='__main__':unittest.main()
