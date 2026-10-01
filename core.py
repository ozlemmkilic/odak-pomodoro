"""Offline persistence and timer logic; Python standard library only."""
import json
import sqlite3
import time
import uuid
import copy
from datetime import datetime, timedelta


def duration(seconds):
    minutes = int(seconds) // 60
    return f'{minutes // 60} sa {minutes % 60:02d} dk'


class Timer:
    def __init__(self, total, clock=time.monotonic):
        self.total = float(total)
        self.elapsed = 0.0
        self.clock = clock
        self.anchor = None
        self.overflow = 0.0

    def resume(self):
        self.anchor = self.clock()

    def advance(self):
        if self.anchor is None:
            return 0.0
        now = self.clock()
        raw = max(0, now - self.anchor)
        delta = min(raw, self.total - self.elapsed)
        self.overflow = raw - delta
        self.elapsed += delta
        self.anchor = now
        return delta

    def pause(self):
        self.advance()
        self.anchor = None


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        existing = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        task_columns={r[1] for r in self.db.execute('PRAGMA table_info(tasks)')}
        if existing and 'target' not in task_columns:
            version='v2' if task_columns else 'v1'
            backup = sqlite3.connect(str(path) + f'.{version}-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
            try:
                self.db.backup(backup)
            finally:
                backup.close()
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS sessions(
          id TEXT PRIMARY KEY, title TEXT NOT NULL, category INTEGER NOT NULL REFERENCES categories(id),
          started TEXT NOT NULL, seconds REAL NOT NULL CHECK(seconds>0), planned REAL NOT NULL,
          status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS allocations(
          session TEXT REFERENCES sessions(id) ON DELETE CASCADE, day TEXT NOT NULL,
          seconds REAL NOT NULL, PRIMARY KEY(session,day));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, category INTEGER NOT NULL REFERENCES categories(id),
          minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 240),
          done INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS session_tasks(
          session TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
          task INTEGER REFERENCES tasks(id));
        ''')
        with self.db:
            columns={r[1] for r in self.db.execute('PRAGMA table_info(tasks)')}
            if 'target' not in columns:self.db.execute('ALTER TABLE tasks ADD COLUMN target INTEGER NOT NULL DEFAULT 1')
            if 'reset_at' not in columns:self.db.execute("ALTER TABLE tasks ADD COLUMN reset_at TEXT NOT NULL DEFAULT ''")
            columns={r[1] for r in self.db.execute('PRAGMA table_info(sessions)')}
            if 'finished_at' not in columns:
                self.db.execute("ALTER TABLE sessions ADD COLUMN finished_at TEXT NOT NULL DEFAULT ''")
                self.db.execute("UPDATE sessions SET finished_at=replace(datetime(started, '+' || seconds || ' seconds'),' ','T')")

    def categories(self):
        return self.db.execute('SELECT * FROM categories ORDER BY name').fetchall()

    def add_category(self, name):
        name = name.strip()
        if not name or len(name) > 60:
            raise ValueError('Başlık 1–60 karakter olmalı.')
        if any(r['name'].casefold() == name.casefold() for r in self.categories()):
            raise ValueError('Bu ana başlık zaten var.')
        with self.db:
            self.db.execute('INSERT INTO categories(name) VALUES(?)', (name,))

    def get(self, key, default=None):
        r = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))

    def save(self, record, clear_active=False):
        if record['seconds'] <= 0:
            raise ValueError('Çalışma süresi sıfırdan büyük olmalı.')
        with self.db:
            self._write_record(record)
            for day, seconds in record['days'].items():
                self.db.execute('INSERT OR REPLACE INTO allocations VALUES(?,?,?)', (record['id'],day,seconds))
            if clear_active:
                self.db.execute('DELETE FROM settings WHERE key="active"')

    def rows(self, start, end, category=None):
        sql = '''SELECT s.*, c.name, SUM(a.seconds) AS period_seconds
                 FROM sessions s JOIN categories c ON c.id=s.category
                 JOIN allocations a ON a.session=s.id WHERE a.day BETWEEN ? AND ?'''
        args = [start,end]
        if category is not None:
            sql += ' AND s.category=?'
            args.append(category)
        return self.db.execute(sql+' GROUP BY s.id ORDER BY s.started DESC', args).fetchall()

    def daily(self, start, end, category=None):
        sql = 'SELECT day,SUM(a.seconds) seconds FROM allocations a JOIN sessions s ON s.id=a.session WHERE day BETWEEN ? AND ?'
        args = [start,end]
        if category is not None:
            sql += ' AND s.category=?'
            args.append(category)
        return self.db.execute(sql+' GROUP BY day ORDER BY day',args).fetchall()

    def delete(self, session_id):
        with self.db:
            self.db.execute('DELETE FROM sessions WHERE id=?',(session_id,))

    def tasks(self):
        return self.db.execute('''SELECT t.*,c.name,
          (SELECT COUNT(*) FROM session_tasks st JOIN sessions s ON s.id=st.session
           WHERE st.task=t.id AND s.finished_at>=t.reset_at) AS rounds
          FROM tasks t JOIN categories c ON c.id=t.category WHERE archived=0
          ORDER BY done,id''').fetchall()

    def task(self, task_id):
        return next((dict(t) for t in self.tasks() if t['id']==task_id), None)

    def save_task(self, title, category, minutes, task_id=None, target=None):
        title=title.strip()
        if not any(r['id']==category for r in self.categories()):
            raise ValueError('Önce bir ana başlık ekle ve seç.')
        if not 1 <= len(title) <= 200:
            raise ValueError('Görev açıklaması 1–200 karakter olmalı.')
        if not 1 <= int(minutes) <= 240:
            raise ValueError('Süre 1–240 dakika arasında olmalı.')
        if target is not None and not 1<=int(target)<=99:raise ValueError('Pomodoro sayısı 1–99 arasında olmalı.')
        with self.db:
            if task_id is None:
                return self.db.execute('INSERT INTO tasks(title,category,minutes,target) VALUES(?,?,?,?)',
                                       (title,category,int(minutes),int(target or 1))).lastrowid
            self.db.execute('UPDATE tasks SET title=?,category=?,minutes=? WHERE id=?',
                            (title,category,int(minutes),task_id))
            if target is not None:self.db.execute('UPDATE tasks SET target=? WHERE id=?',(int(target),task_id))
            return task_id

    def reset_tasks(self, now=None, daily=False):
        now=now or datetime.now()
        cutoff=now.replace(hour=0,minute=0,second=0,microsecond=0) if daily else now
        with self.db:
            self.db.execute('UPDATE tasks SET done=0,reset_at=? WHERE archived=0',(cutoff.isoformat(),))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('task_day',json.dumps(now.date().isoformat())))

    def ensure_task_day(self,now=None):
        now=now or datetime.now()
        if self.get('daily_reset',True) and self.get('task_day')!=now.date().isoformat():
            self.reset_tasks(now,daily=True); return True
        return False

    def _write_record(self,work):
        finished=work.get('finished_at') or (datetime.fromisoformat(work['started'])+timedelta(seconds=work['seconds'])).isoformat()
        self.db.execute('''INSERT INTO sessions(id,title,category,started,seconds,planned,status,finished_at)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET seconds=excluded.seconds,
          status=excluded.status''',
          tuple(work[k] for k in ('id','title','category','started','seconds','planned','status'))+(finished,))

    def update_task(self, task_id, *, done=None, archived=None):
        with self.db:
            if done is not None: self.db.execute('UPDATE tasks SET done=? WHERE id=?',(int(done),task_id))
            if archived is not None: self.db.execute('UPDATE tasks SET archived=? WHERE id=?',(int(archived),task_id))

    def finish_phase(self, work, task_id, next_state, cycles, continuation=None):
        """Commit the record AND next phase together; completion cannot be duplicated."""
        with self.db:
            if work and work['seconds'] > 0:
                self._write_record(work)
                for day, seconds in work['days'].items():
                    self.db.execute('INSERT OR REPLACE INTO allocations VALUES(?,?,?)',(work['id'],day,seconds))
                if task_id is not None:
                    self.db.execute('INSERT OR IGNORE INTO session_tasks VALUES(?,?)',(work['id'],task_id))
            for key,value in (('active_v2',next_state),('cycles',cycles),('active',None),('continuation',continuation)):
                self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))


class OvertimeTimer(Timer):
    def advance(self):
        if self.anchor is None:return 0.0
        now=self.clock(); delta=max(0,now-self.anchor); self.anchor=now
        self.elapsed+=delta; self.overflow=0.0; return delta


def planned_seconds(minutes,count,cycles=0,short=5,long=15,every=4,include_breaks=True):
    """Work plus breaks BETWEEN sessions, never a break after the final session."""
    seconds=minutes*60*count
    if include_breaks:
        for i in range(1,count):seconds+=(long if (cycles+i)%every==0 else short)*60
    return seconds


class Engine:
    """One timer shared by the main window and desktop widget."""
    def __init__(self, store, clock=time.monotonic, wall_clock=datetime.now):
        self.store=store; self.clock=clock; self.wall_clock=wall_clock
        self.timer=None; self.work=None; self.task_id=None; self.mode='work'
        self.cycles=store.get('cycles',0)
        self.continuation=store.get('continuation')
        self.last_checkpoint=-1
        state=store.get('active_v2')
        old=store.get('active')
        if not state and old:
            state=dict(mode='work',total=old['planned'],elapsed=old['seconds'],work=old,task_id=None)
        if state:
            self.mode=state['mode']; self.work=state.get('work'); self.task_id=state.get('task_id')
            self.timer=(OvertimeTimer if self.mode=='overtime' else Timer)(state['total'],clock)
            self.timer.elapsed=state['elapsed'] if self.mode=='overtime' else min(state['elapsed'],state['total'])
            self.checkpoint()
            store.set('active',None)

    def payload(self):
        if not self.timer: return None
        return dict(mode=self.mode,total=self.timer.total,elapsed=self.timer.elapsed,work=self.work,task_id=self.task_id)

    def checkpoint(self):
        self.store.set('active_v2',self.payload())

    def start_work(self, task):
        if self.timer: raise ValueError('Önce mevcut oturumu bitir veya iptal et.')
        self._start_task(task)

    def _start_task(self, task):
        work=record(task['title'],task['category'],self.wall_clock(),task['minutes'])
        state=dict(mode='work',total=task['minutes']*60,elapsed=0,work=work,task_id=task['id'])
        # Persist before replacing the live timer; a failed write leaves it recoverable.
        self.store.finish_phase(None,None,state,self.cycles,None)
        self.task_id=task['id']; self.mode='work'
        self.work=work
        self.timer=Timer(task['minutes']*60,self.clock); self.timer.resume()
        self.continuation=None; self.last_checkpoint=-1

    def _new_break(self, long_break=False, running=True):
        self.mode='long' if long_break else 'short'; self.work=None
        mins=self.store.get('long_break',15) if long_break else self.store.get('break',5)
        self.timer=Timer(mins*60,self.clock)
        if running: self.timer.resume()

    def start_break(self, long_break=False):
        if self.timer: raise ValueError('Önce mevcut oturumu bitir veya iptal et.')
        self._new_break(long_break); self.checkpoint()

    def _advance(self):
        if not self.timer: return
        delta=self.timer.advance()
        if self.work and delta:
            allocate(self.work['days'],self.wall_clock()-timedelta(seconds=self.timer.overflow),delta)
            self.work['seconds']=self.timer.elapsed
            if self.mode!='overtime' and self.timer.elapsed>=self.timer.total:
                self.work['finished_at']=(self.wall_clock()-timedelta(seconds=self.timer.overflow)).isoformat()

    def tick(self):
        if not self.timer: return None
        self._advance()
        if self.mode!='overtime' and self.timer.elapsed >= self.timer.total:
            return self.finish(completed=True)
        check=int(self.timer.elapsed)//5
        if check!=self.last_checkpoint:
            self.checkpoint(); self.last_checkpoint=check
        return None

    def pause_resume(self):
        if not self.timer: return
        if self.timer.anchor is not None:
            self._advance(); self.timer.anchor=None
        else: self.timer.resume()
        self.checkpoint()

    def finish(self, completed=False):
        if not self.timer: return None
        self._advance()
        completed=completed or self.timer.elapsed>=self.timer.total
        work=self.work; tid=self.task_id; old_mode=self.mode
        next_cycles=self.cycles
        if work:
            work['status']='Uzatıldı' if old_mode=='overtime' else 'Tamamlandı' if completed else 'Erken bitirildi'
            if old_mode!='overtime':
                work['finished_at']=work.get('finished_at') or self.wall_clock().isoformat()
                if work['seconds']>0:next_cycles+=1
        # Construct the next state without starting its clock until the commit succeeds.
        next_state=None
        if work and completed:
            is_long=next_cycles % self.store.get('long_every',4)==0
            mins=self.store.get('long_break',15) if is_long else self.store.get('break',5)
            next_state=dict(mode='long' if is_long else 'short',total=mins*60,elapsed=0,work=None,task_id=tid)
        continuation=self.continuation
        if work:
            continuation=dict(work=copy.deepcopy(work),task_id=tid) if completed else None
        self.store.finish_phase(work,tid,next_state,next_cycles,continuation)
        self.continuation=continuation
        self.cycles=next_cycles; self.work=None; self.timer=None; self.mode='work'; self.last_checkpoint=-1
        if next_state:
            self.mode=next_state['mode']; self.timer=Timer(next_state['total'],self.clock)
            if self.store.get('auto_break',True): self.timer.resume()
        return 'extended' if old_mode=='overtime' else 'work_done' if old_mode=='work' and completed else ('break_done' if old_mode!='work' else 'saved')

    def can_continue(self):
        return bool(self.continuation and self.mode in ('work','short','long') and not self.work
                    and self.store.db.execute('SELECT 1 FROM sessions WHERE id=?',(self.continuation['work']['id'],)).fetchone())

    def continue_work(self):
        if not self.can_continue():raise ValueError('Devam ettirilebilecek tamamlanmış oturum yok.')
        work=copy.deepcopy(self.continuation['work'])
        state=dict(mode='overtime',total=work['planned'],elapsed=work['seconds'],work=work,task_id=self.continuation['task_id'])
        self.store.set('active_v2',state)
        self.mode='overtime'; self.work=work; self.task_id=state['task_id']
        self.timer=OvertimeTimer(work['planned'],self.clock); self.timer.elapsed=work['seconds']; self.timer.resume()
        self.last_checkpoint=-1

    def restart(self):
        if not self.timer:return
        if self.mode in ('short','long'):
            self._new_break(self.mode=='long'); self.checkpoint(); return
        task=self.store.task(self.task_id)
        if not task:raise ValueError('Yeniden başlatmak için bu görev listede olmalı.')
        # Completed base record remains if only the overtime portion is discarded.
        self._start_task(task)

    def cancel(self):
        self.store.finish_phase(None,None,None,self.cycles)
        self.timer=None; self.work=None; self.mode='work'; self.last_checkpoint=-1; self.continuation=None

    def close(self):
        self._advance()
        if self.timer: self.timer.anchor=None
        self.checkpoint()


def allocate(days, end, seconds):
    """Split actual focused time across local calendar dates, including midnight."""
    cursor = end - timedelta(seconds=seconds)
    while seconds > 0.000001:
        midnight = datetime.combine(cursor.date()+timedelta(days=1), datetime.min.time())
        part = min(seconds, (midnight-cursor).total_seconds())
        key = cursor.date().isoformat()
        days[key] = days.get(key,0)+part
        cursor += timedelta(seconds=part)
        seconds -= part


def record(title, category, start, minutes):
    return dict(id=uuid.uuid4().hex, title=title.strip(), category=category,
                started=start.isoformat(timespec='seconds'), seconds=0.0,
                planned=minutes*60, status='Tamamlandı', days={})
