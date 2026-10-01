"""Odak 2: offline native desktop UI."""
import csv
import math
import os
import sys
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from PySide6.QtCore import Qt, QTimer, QRectF, QSize, QDate, QDateTime
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QIcon, QLinearGradient
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,
 QVBoxLayout,QHBoxLayout,QGridLayout,QStackedWidget,QScrollArea,QComboBox,QSpinBox,
 QLineEdit,QDialog,QDialogButtonBox,QFormLayout,QCheckBox,QListWidget,QListWidgetItem,
 QMessageBox,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,
 QDateEdit,QDateTimeEdit,QProgressBar,QMenu,QInputDialog,QTextBrowser)
from core import Store,Engine,duration,record,allocate,planned_seconds

THEMES={
 'dark':dict(bg='#0f121b',card='#171b26',deep='#0b0f17',field='#222735',border='#2d3342',text='#eef1f8',muted='#9ca7bb',accent='#2cff05',soft='#16371b',ink='#102408',link='#2cff05'),
 'light':dict(bg='#f5f6f8',card='#ffffff',deep='#fffaf0',field='#f1f3f7',border='#e0e4eb',text='#202734',muted='#626d7e',accent='#ffa500',soft='#fff0d3',ink='#3b2600',link='#935500')}

def label(text='',role='',wrap=False):
    w=QLabel(text); w.setTextFormat(Qt.PlainText); w.setObjectName(role); w.setWordWrap(wrap); return w

def button(text,action,role='secondary',tip=''):
    b=QPushButton(text); b.setObjectName(role); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(action); b.setToolTip(tip); return b

def card(title=''):
    w=QFrame(); w.setObjectName('card'); l=QVBoxLayout(w); l.setContentsMargins(20,20,20,20); l.setSpacing(14)
    if title:l.addWidget(label(title,'cardTitle'))
    return w,l

def spin(value,maximum=240,suffix=' dk'):
    s=QSpinBox(); s.setRange(1,maximum); s.setValue(value); s.setSuffix(suffix); return s

class Ring(QWidget):
    def __init__(self,owner):
        super().__init__(); self.owner=owner; self.setMinimumSize(295,310)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); c=dict(self.owner.colors)
        overtime=self.owner.engine.mode=='overtime'
        if overtime:c.update(accent='#9457eb',link='#9457eb')
        side=min(self.width()-38,self.height()-30,380); r=QRectF((self.width()-side)/2,(self.height()-side)/2,side,side)
        e=self.owner.engine; t=e.timer; ratio=1 if overtime else max(0,1-t.elapsed/t.total) if t else 1
        for width,alpha in ((26,8),(19,12)):
            col=QColor(c['accent']); col.setAlpha(alpha); p.setPen(QPen(col,width)); p.drawEllipse(r)
        p.setPen(QPen(QColor(c['border']),10)); p.drawEllipse(r)
        pen=QPen(QColor(c['accent']),10); pen.setCapStyle(Qt.RoundCap); p.setPen(pen); p.drawArc(r,90*16,-int(ratio*359.9*16))
        p.setPen(QColor(c['muted'])); p.setFont(QFont('Segoe UI',9 if side>260 else 8)); p.drawText(QRectF(r.x(),r.center().y()-min(70,side*.30),side,20),Qt.AlignCenter,'TOPLAM ÇALIŞMA' if overtime else 'KALAN SÜRE')
        p.setPen(QColor(c['text'])); p.setFont(QFont('Consolas',int(side/6.4),QFont.Bold)); p.drawText(QRectF(r.x()-10,r.center().y()-43,side+20,90),Qt.AlignCenter,self.owner.time_text())
        p.setPen(QColor(c['link'])); p.setFont(QFont('Segoe UI',11 if side>260 else 8)); text={'work':'Bir göreve, tam odak.','short':'Kısa bir nefes al.','long':'Yenilenme zamanı.','overtime':f"+{int(max(0,t.elapsed-t.total))//60:02d}:{int(max(0,t.elapsed-t.total))%60:02d} uzatma" if t else ''}[e.mode]
        p.drawText(QRectF(r.x(),r.center().y()+min(55,side*.20),side,20),Qt.AlignCenter,text)

class Chart(QWidget):
    def __init__(self,owner,kind):
        super().__init__(); self.owner=owner; self.kind=kind; self.data=[]; self.setMinimumHeight(145 if kind=='heat' else 235)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); c=self.owner.colors; w,h=self.width(),self.height(); p.setFont(QFont('Segoe UI',8))
        if self.kind=='trend':
            goal=self.owner.store.get('goal',120)/60; top=max(1,goal,max((v for _,v in self.data),default=0))*1.2; bottom=h-30; scale=(h-50)/top
            for i in range(4):
                val=top*i/3; y=bottom-val*scale; p.setPen(QColor(c['border'])); p.drawLine(34,int(y),w-8,int(y)); p.setPen(QColor(c['muted'])); p.drawText(QRectF(0,y-9,27,18),Qt.AlignRight,f'{val:.1f}')
            p.setPen(QPen(QColor(c['accent']),1,Qt.DashLine)); p.drawLine(34,int(bottom-goal*scale),w-8,int(bottom-goal*scale))
            step=(w-48)/max(1,len(self.data))
            for i,(day,val) in enumerate(self.data):
                x=36+i*step+step*.16; height=val*scale; grad=QLinearGradient(0,bottom-height,0,bottom); grad.setColorAt(0,QColor(c['accent'])); grad.setColorAt(1,QColor(c['soft']))
                p.setPen(Qt.NoPen); p.setBrush(grad)
                if height:p.drawRoundedRect(QRectF(x,bottom-height,step*.64,height),4,4)
                p.setPen(QColor(c['muted']))
                if len(self.data)<=7 or i%5==0 or i==len(self.data)-1:p.drawText(QRectF(x-12,bottom+7,step*.64+24,20),Qt.AlignCenter,day.strftime('%d.%m'))
                if len(self.data)<=7 and val:p.drawText(QRectF(x-12,bottom-height-23,step*.64+24,20),Qt.AlignCenter,f'{val:.1f}s')
            if not any(v for _,v in self.data):p.drawText(self.rect(),Qt.AlignCenter,'İlk çalışmandan sonra grafik burada oluşacak.')
        elif self.kind=='donut':
            side=min(140,w*.38); r=QRectF(14,(h-side)/2,side,side); total=sum(v for _,v in self.data); pos=90*16
            p.setPen(QPen(QColor(c['border']),17)); p.drawEllipse(r)
            for i,(name,val) in enumerate(self.data):
                color=QColor(c['accent']); color.setAlpha(max(70,255-i*32)); angle=int(val/total*360*16) if total else 0
                p.setPen(QPen(color,17)); p.drawArc(r,pos,-angle); pos-=angle
                x=int(side+43); y=30+i*32; p.setPen(Qt.NoPen); p.setBrush(color); p.drawEllipse(x,y+4,8,8); p.setPen(QColor(c['text']))
                title=p.fontMetrics().elidedText(name,Qt.ElideRight,max(40,w-x-75)); p.drawText(x+15,y+14,title); p.drawText(QRectF(w-55,y,50,20),Qt.AlignRight,f'%{val/total*100:.0f}')
            p.setPen(QColor(c['text'])); p.setFont(QFont('Segoe UI',24,QFont.Bold)); p.drawText(r,Qt.AlignCenter,f'{total/3600:.1f}'); p.setFont(QFont('Segoe UI',8)); p.setPen(QColor(c['muted'])); p.drawText(QRectF(r.x(),r.center().y()+22,side,18),Qt.AlignCenter,'TOPLAM SAAT')
            if not self.data:p.drawText(QRectF(side+40,80,w-side-45,60),Qt.AlignCenter,'Henüz kayıt yok')
        else:
            values=dict(self.data); today=date.today(); start=today-timedelta(days=today.weekday(),weeks=7); step=(w-34)/8; maximum=max(3600,max(values.values(),default=0))
            for row,name in enumerate(('Pzt','Sal','Çar','Per','Cum','Cmt','Paz')):
                y=row*20; p.setPen(QColor(c['muted'])); p.drawText(0,y+13,name)
                for week in range(8):
                    day=start+timedelta(days=week*7+row); val=values.get(day.isoformat(),0); color=QColor(c['border'])
                    if val:color=QColor(c['accent']); color.setAlpha(int(55+200*min(1,val/maximum)))
                    if day>today:color.setAlpha(40)
                    p.setPen(Qt.NoPen); p.setBrush(color); p.drawRoundedRect(QRectF(34+week*step,y,step-5,16),3,3)

class MiniWidget(QWidget):
    def __init__(self,owner):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint); self.owner=owner; self.drag=None; self.setObjectName('mini'); self.setFixedSize(350,290); self.setWindowTitle('Odak Widget')
        self.setWindowFlag(Qt.WindowStaysOnTopHint,owner.store.get('widget_top',True)); root=QVBoxLayout(self); root.setContentsMargins(18,14,18,16)
        head=QHBoxLayout(); self.phase=label('● ODAK','accentLabel'); head.addWidget(self.phase); head.addStretch(); head.addWidget(button('↗',self.restore,'small','Ana pencereyi göster')); head.addWidget(button('×',self.close,'small','Widget’ı kapat')); root.addLayout(head)
        self.task=label('','muted'); root.addWidget(self.task); self.clock=label('','miniClock'); self.clock.setAlignment(Qt.AlignCenter); root.addWidget(self.clock)
        self.bar=QProgressBar(); self.bar.setTextVisible(False); self.bar.setMaximum(1000); root.addWidget(self.bar)
        row=QHBoxLayout(); self.toggle=button('Başlat',owner.toggle_timer,'primary'); row.addWidget(self.toggle,1); row.addWidget(button('Bitir',owner.finish_early)); root.addLayout(row)
        row=QHBoxLayout(); self.extend=button('Devam ettir +',owner.continue_work,'purple'); row.addWidget(self.extend); self.reset=button('Sıfırla',owner.cancel_timer); row.addWidget(self.reset); root.addLayout(row)
        screen=QApplication.primaryScreen().availableGeometry(); pos=owner.store.get('widget_pos',[screen.right()-350,screen.bottom()-260]); self.move(max(screen.left(),min(pos[0],screen.right()-330)),max(screen.top(),min(pos[1],screen.bottom()-240)))
    def sync(self):
        e=self.owner.engine; self.clock.setText(self.owner.time_text()); self.phase.setText('● '+{'work':'ODAK','short':'KISA MOLA','long':'UZUN MOLA','overtime':'UZATMA'}[e.mode]); title=e.work['title'] if e.work else self.owner.selected_title(); self.task.setText(self.task.fontMetrics().elidedText(title,Qt.ElideRight,285)); self.toggle.setText(self.owner.toggle_text()); self.bar.setValue(1000 if e.mode=='overtime' else int(1000*(1-e.timer.elapsed/e.timer.total)) if e.timer else 1000)
        self.extend.setEnabled(e.can_continue()); self.reset.setEnabled(e.timer is not None)
        self.clock.setStyleSheet('color:#9457eb;' if e.mode=='overtime' else '')
        self.bar.setStyleSheet('QProgressBar::chunk {background:#9457eb;}' if e.mode=='overtime' else '')
    def restore(self):self.owner.showNormal(); self.owner.raise_(); self.owner.activateWindow()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self.drag=event.globalPosition().toPoint()-self.pos()
    def mouseMoveEvent(self,event):
        if self.drag is not None:self.move(event.globalPosition().toPoint()-self.drag)
    def mouseReleaseEvent(self,event):self.drag=None; self.owner.store.set('widget_pos',[self.x(),self.y()])
    def closeEvent(self,event):
        if not self.owner.closing and not self.owner.isVisible():self.restore()
        self.owner.store.set('widget_pos',[self.x(),self.y()]); super().closeEvent(event)

class MainWindow(QMainWindow):
    def __init__(self,data_path=None):
        super().__init__(); self.setWindowTitle('Odak • Pomodoro & Çalışma Günlüğü'); self.resize(1440,940); self.setMinimumSize(1060,700)
        self.data_path=Path(data_path) if data_path else data_directory()/'odak.sqlite3'; self.store=Store(self.data_path); self.store.ensure_task_day(); self.engine=Engine(self.store)
        self.selected_id=self.engine.task_id; self.widget=None; self.closing=False; self.refreshing=False; self.categories={}; self.nav=[]; self.compact=None
        self.theme=self.store.get('theme','dark'); self.colors=THEMES.get(self.theme,THEMES['dark'])
        self.build(); self.apply_theme(self.theme); self.refresh_categories(); self.refresh_all()
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(200)
        if self.engine.timer:self.notify('Yarım kalan oturum duraklatılmış olarak geri yüklendi. Devam et ile sürdürebilirsin.')
        elif not self.categories:self.notify('Hoş geldin! Görev ekle ile ilk ana başlığını ve çalışma planını oluştur. Verilerin yalnızca bu bilgisayarda tutulur.')
    def build(self):
        central=QWidget(); self.setCentralWidget(central); layout=QVBoxLayout(central); layout.setContentsMargins(24,16,24,12); layout.setSpacing(16)
        head=QHBoxLayout(); head.setSpacing(10); head.addWidget(label('◉  odak.','brand')); self.status=label('● HAZIR','badge'); head.addWidget(self.status); head.addStretch()
        for i,title in enumerate(('Pomodoro','Dashboard','Geçmiş','Ayarlar')):
            b=button(title,lambda checked=False,i=i:self.change_page(i),'nav'); b.setCheckable(True); self.nav.append(b); head.addWidget(b)
        head.addStretch(); self.theme_box=QComboBox(); self.theme_box.addItems(['Koyu tema','Açık tema']); self.theme_box.setCurrentIndex(self.theme=='light'); self.theme_box.currentIndexChanged.connect(lambda i:self.apply_theme('light' if i else 'dark')); head.addWidget(self.theme_box); head.addWidget(button('▣ Widget',self.show_widget)); layout.addLayout(head)
        self.banner=label('','notice',True); self.banner.hide(); layout.addWidget(self.banner); self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        self.build_focus(); self.build_dashboard(); self.build_history(); self.build_settings()
        foot=QHBoxLayout(); foot.addWidget(label('Bitir: kaydet • Sıfırla: kaydetmeden yeniden başlat','muted')); foot.addStretch(); foot.addWidget(label('ODAK 2.2 • Verilerin bu bilgisayarda','muted')); layout.addLayout(foot); self.change_page(0)
    def page(self):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(0,2,0,4); layout.setSpacing(20); scroll.setWidget(content); self.stack.addWidget(scroll); return layout
    def build_focus(self):
        root=self.page(); modes=QHBoxLayout(); modes.addStretch(); self.mode_buttons=[]
        for key,title in [('work','● Odaklanma'),('short','☕ Kısa mola'),('long','☕ Uzun mola')]:
            b=button(title,lambda checked=False,k=key:self.select_mode(k),'mode'); b.setCheckable(True); modes.addWidget(b); self.mode_buttons.append((key,b))
        modes.addStretch(); root.addLayout(modes); grid=QGridLayout(); self.focus_grid=grid; grid.setSpacing(18)
        for i,s in enumerate((3,6,3)):grid.setColumnStretch(i,s)
        left=QVBoxLayout(); left.setSpacing(18); goal,l=card('⚑  Günlük hedef'); self.goal_text=label('','statValue'); l.addWidget(self.goal_text); self.goal_bar=QProgressBar(); self.goal_bar.setTextVisible(False); l.addWidget(self.goal_bar); self.goal_hint=label('','muted',True); l.addWidget(self.goal_hint); left.addWidget(goal)
        tasks,l=card('✓  Yapılacaklarım'); self.task_summary=label('','muted'); l.addWidget(self.task_summary); self.tasks=QListWidget(); self.tasks.setObjectName('tasks'); self.tasks.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.tasks.setMinimumHeight(240); self.tasks.currentItemChanged.connect(self.task_selected); l.addWidget(self.tasks,1); l.addWidget(button('+  Görev ekle',self.task_dialog,'primary'))
        row=QHBoxLayout(); row.addWidget(button('Düzenle',self.edit_task,'small')); row.addWidget(button('+ Ana başlık',self.add_category,'small')); l.addLayout(row)
        l.addWidget(button('↺ Görevleri sıfırla',self.reset_tasks,'small'))
        self.daily_reset=QCheckBox('Her yeni günde sıfırla'); self.daily_reset.setChecked(self.store.get('daily_reset',True)); self.daily_reset.toggled.connect(self.set_daily_reset); l.addWidget(self.daily_reset); left.addWidget(tasks,1)
        tip,l=card(); self.focus_tip=tip; l.addWidget(label('Bir adım yeter.','accentLabel')); l.addWidget(label('Bir görev için birden fazla Pomodoro yapabilirsin. Görev bittiğinde kutucuğunu işaretle.','muted',True)); left.addWidget(tip); grid.addLayout(left,0,0)
        center,l=card(); self.timer_card=center; self.center_layout=l; center.setObjectName('timerCard'); self.active_title=label('Bir görev seç','activeTitle',True); self.active_title.setAlignment(Qt.AlignCenter); l.addWidget(self.active_title); self.active_category=label('','muted'); self.active_category.setAlignment(Qt.AlignCenter); l.addWidget(self.active_category); self.ring=Ring(self); l.addWidget(self.ring,1)
        presets=QHBoxLayout(); presets.addStretch(); self.presets=[]
        for n in (15,25,30,45,60):
            b=button(str(n),lambda checked=False,n=n:self.work_minutes.setValue(n),'preset'); self.presets.append(b); presets.addWidget(b)
        presets.addStretch(); l.addLayout(presets); custom=QHBoxLayout(); custom.addStretch(); custom.addWidget(label('Görevin süresi','muted')); self.work_minutes=spin(30); self.work_minutes.setMaximumWidth(110); self.work_minutes.valueChanged.connect(self.duration_changed); custom.addWidget(self.work_minutes); custom.addStretch(); l.addLayout(custom)
        controls=QHBoxLayout(); self.cancel_button=button('↺ Sıfırla',self.cancel_timer,'small','Geçen süreyi kaydetmeden aynı süreyi yeniden başlat'); controls.addWidget(self.cancel_button); self.start_button=button('▶ Başlat',self.toggle_timer,'primary'); self.start_button.setMinimumHeight(54); controls.addWidget(self.start_button,1); self.finish_button=button('✓ Bitir',self.finish_early,tip='Bir Pomodoro say ve gerçekten geçen süreyi kaydet'); controls.addWidget(self.finish_button); l.addLayout(controls)
        self.continue_button=button('Devam ettir +  •  Son Pomodoro’yu uzat',self.continue_work,'purple'); self.continue_button.hide(); l.addWidget(self.continue_button)
        self.eta_label=label('','muted',True); self.eta_label.setAlignment(Qt.AlignCenter); l.addWidget(self.eta_label)
        self.next_phase=label('','muted',True); self.next_phase.setAlignment(Qt.AlignCenter); l.addWidget(self.next_phase); self.cycle_label=label('','accentLabel'); self.cycle_label.setAlignment(Qt.AlignCenter); l.addWidget(self.cycle_label); grid.addWidget(center,0,1)
        right=QVBoxLayout(); right.setSpacing(18); phase,l=card('☕  Mola akışı'); self.phase_intro=label('Odaklan. Zil çalsın.\nMolan başlasın.','cardTitle',True); l.addWidget(self.phase_intro); self.break_info=label('','muted',True); l.addWidget(self.break_info)
        self.auto_break=QCheckBox('Molayı otomatik başlat'); self.auto_break.setChecked(self.store.get('auto_break',True)); self.auto_break.toggled.connect(lambda v:self.store.set('auto_break',v)); l.addWidget(self.auto_break); l.addWidget(button('Mola sürelerini ayarla',lambda:self.change_page(3))); right.addWidget(phase)
        sound,l=card('♫  Sesli bildirim'); self.sound=QCheckBox('Süre bitince zil çal'); self.sound.setChecked(self.store.get('sound',True)); self.sound.toggled.connect(lambda v:self.store.set('sound',v)); l.addWidget(self.sound); l.addWidget(button('Zili dene',lambda:self.play_alarm(True))); self.sound_help=label('Odak ve mola sonunda çalar. Bilgisayar sesinin açık olduğundan emin ol.','muted',True); l.addWidget(self.sound_help); right.addWidget(sound)
        mini,l=card('▣  Masaüstü widget'); self.widget_help=label('Başka bir uygulamada çalışırken sayacın yanında kalsın.','muted',True); l.addWidget(self.widget_help); l.addWidget(button('Widget’ı göster',self.show_widget,'primary')); l.addWidget(button('Widget’a küçült',self.minimize_to_widget)); self.pin=QCheckBox('Her zaman üstte tut'); self.pin.setChecked(self.store.get('widget_top',True)); self.pin.toggled.connect(self.set_widget_top); l.addWidget(self.pin); right.addWidget(mini); right.addStretch(); grid.addLayout(right,0,2); root.addLayout(grid,1)
        stats=QHBoxLayout(); self.focus_stats=[]
        for title in ('BUGÜNKÜ ODAK','TAMAMLANAN POMODORO','AKTİF GÜN SERİSİ','BEKLEYEN GÖREV'):
            f,l=card(); l.addWidget(label(title,'muted')); value=label('0','statValue'); l.addWidget(value); self.focus_stats.append(value); stats.addWidget(f)
        root.addLayout(stats)
    def build_dashboard(self):
        root=self.page(); top=QHBoxLayout(); titles=QVBoxLayout(); titles.addWidget(label('İLERLEMENİ GÖR','accentLabel')); titles.addWidget(label('Analitik ve çalışma ritmin','pageTitle')); top.addLayout(titles); top.addStretch(); self.period=QComboBox(); self.period.addItems(['Bugün','Son 7 gün','Son 30 gün','Bu ay','Tüm zamanlar']); self.period.setCurrentIndex(1); self.period.currentIndexChanged.connect(self.refresh_dashboard); top.addWidget(self.period); self.dash_category=QComboBox(); self.dash_category.currentIndexChanged.connect(self.refresh_dashboard); top.addWidget(self.dash_category); root.addLayout(top)
        stats=QHBoxLayout(); self.dash_stats=[]
        for title in ('TOPLAM ODAK SÜRESİ','TAMAMLANAN POMODORO','AKTİF GÜN','GÜNLÜK ORTALAMA'):
            f,l=card(); l.addWidget(label(title,'muted')); v=label('0','statValue'); l.addWidget(v); stats.addWidget(f); self.dash_stats.append(v)
        root.addLayout(stats); charts=QHBoxLayout(); f,l=card('Günlük çalışma trendi'); self.trend_hint=label('','muted',True); l.addWidget(self.trend_hint); self.trend=Chart(self,'trend'); l.addWidget(self.trend); charts.addWidget(f,3); f,l=card('Konu ve kategori dağılımı'); l.addWidget(label('Seçilen dönemde kaydedilen süreler','muted')); self.donut=Chart(self,'donut'); l.addWidget(self.donut); charts.addWidget(f,2); root.addLayout(charts)
        f,l=card('Aktivite matrisi • son 8 hafta'); l.addWidget(label('Renk yoğunluğu günlük çalışma süreni gösterir. Konu filtresi uygulanır.','muted',True)); self.heat=Chart(self,'heat'); l.addWidget(self.heat); root.addWidget(f); self.category_table=self.table(['Ana başlık','Çalışma süresi','Pay']); self.category_table.setMinimumHeight(180); root.addWidget(self.category_table); root.addWidget(label('Kısmi ve elle eklenen çalışmalar süreye dahildir. Molalar çalışma toplamına eklenmez.','muted',True))
    def build_history(self):
        root=self.page(); top=QHBoxLayout(); top.addWidget(label('Çalışma günlüğü','pageTitle')); top.addStretch(); top.addWidget(button('+ Geçmiş çalışma ekle',self.manual_dialog,'primary')); top.addWidget(button('CSV dışa aktar',self.export)); root.addLayout(top)
        row=QHBoxLayout(); self.from_date=QDateEdit(QDate.currentDate().addDays(1-QDate.currentDate().day())); self.to_date=QDateEdit(QDate.currentDate())
        for title,field in [('Başlangıç',self.from_date),('Bitiş',self.to_date)]:
            row.addWidget(label(title,'muted')); field.setCalendarPopup(True); field.setDisplayFormat('dd.MM.yyyy'); field.dateChanged.connect(self.refresh_history); row.addWidget(field)
        self.search=QLineEdit(); self.search.setPlaceholderText('Görev veya konu ara…'); self.search.textChanged.connect(self.refresh_history); row.addWidget(self.search,1); row.addWidget(button('Tüm kayıtlar',self.all_history)); root.addLayout(row); self.history=self.table(['Tarih / saat','Oturum açıklaması','Ana başlık','Süre','Durum']); self.history.setMinimumHeight(380); root.addWidget(self.history,1); row=QHBoxLayout(); self.history_hint=label('','muted',True); row.addWidget(self.history_hint,1); row.addWidget(button('Seçili kaydı sil',self.delete_record)); root.addLayout(row)
    def build_settings(self):
        # Privacy text and bundled dependency notices are available offline.
        root=self.page(); root.addWidget(label('Kendi ritmini belirle','pageTitle')); f,l=card('Süreler ve günlük hedef'); form=QFormLayout(); form.setSpacing(18); self.goal_input=spin(self.store.get('goal',120),1440); self.short_input=spin(self.store.get('break',5)); self.long_input=spin(self.store.get('long_break',15)); self.every_input=spin(self.store.get('long_every',4),12,' Pomodoro')
        for title,field in [('Günlük çalışma hedefi',self.goal_input),('Kısa mola',self.short_input),('Uzun mola',self.long_input),('Uzun mola sıklığı',self.every_input)]:form.addRow(title,field)
        l.addLayout(form); l.addWidget(button('Ayarları kaydet',self.save_settings,'primary')); root.addWidget(f)
        f,l=card('Ana başlıklar'); l.addWidget(label('Görevlerini kendi belirlediğin ana başlıklar altında grupla. Her başlık için toplam çalışma süreni Dashboard’da görebilirsin.','muted',True)); self.category_names=label('','accentLabel',True); l.addWidget(self.category_names); l.addWidget(button('+ Ana başlık ekle',self.add_category)); root.addWidget(f)
        f,l=card('Veriler ve yedekleme'); l.addWidget(label('Kayıtların bu bilgisayarda saklanır. CSV dışa aktarabilir veya veritabanını yedekleyebilirsin.','muted',True)); l.addWidget(button('Veritabanını yedekle',self.backup)); l.addWidget(button('Hakkında • Gizlilik ve lisanslar',self.show_information)); path=label(str(self.data_path),'muted',True); path.setTextInteractionFlags(Qt.TextSelectableByMouse); l.addWidget(path); root.addWidget(f)
        f,l=card('Nasıl kullanılır?'); l.addWidget(label('1. Görev ekle: süreyi ve kaç Pomodoro planladığını seç; tahmini bitişi gör.\n2. Bitir: erken de olsa 1 Pomodoro sayılır, geçen süre kaydedilir.\n3. Sıfırla: kaydetmeden aynı süreyle yeniden başlatır.\n4. Süre dolunca Devam ettir: mor sayaç 30:00 üzerinden ilerler, aynı kayda eklenir.\n5. Görevleri sıfırla: işaretleri ve görev tur sayaçlarını yeniler; geçmiş kalır.\n6. Dışarıda yaptığın çalışmayı Geçmiş çalışma ekle ile gerçek süresiyle gir.','muted',True)); root.addWidget(f); root.addStretch()
    def show_information(self):
        d=QDialog(self); d.setWindowTitle('Odak 2.2 • Gizlilik ve lisanslar'); d.resize(660,560)
        layout=QVBoxLayout(d); text=QTextBrowser(); text.setOpenExternalLinks(False)
        sections=[]
        for filename in ('GIZLILIK.txt','THIRD_PARTY_NOTICES.txt'):
            p=Path(__file__).parent/filename
            if p.exists():sections.append(p.read_text(encoding='utf-8'))
        text.setPlainText('\n\n'.join(sections)); layout.addWidget(text)
        layout.addWidget(button('Kapat',d.accept)); d.exec()
    def table(self,columns):
        t=QTableWidget(0,len(columns)); t.setHorizontalHeaderLabels(columns); t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSelectionMode(QAbstractItemView.SingleSelection); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.setAlternatingRowColors(True); t.setShowGrid(False); t.verticalHeader().hide(); t.verticalHeader().setDefaultSectionSize(44); t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); return t
    def fill_table(self,table,rows):
        table.setRowCount(len(rows))
        for i,values in enumerate(rows):
            for j,v in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(v)))
    def apply_theme(self,theme):
        self.theme=theme; self.colors=THEMES[theme]; self.store.set('theme',theme); c=self.colors; check=(Path(__file__).parent/'check.svg').as_posix()
        QApplication.instance().setStyleSheet(f'''
        QWidget {{background:{c['bg']};color:{c['text']};font-family:'Segoe UI';font-size:13px;}}
        QFrame#card {{background:{c['card']};border:1px solid {c['border']};border-radius:18px;}}
        QFrame#timerCard {{background:{c['deep']};border:1px solid {c['border']};border-radius:22px;}}
        QLabel {{background:transparent;border:0;}} QLabel#brand {{font-size:26px;font-weight:800;}}
        QLabel#badge {{color:{c['link']};background:{c['soft']};border-radius:10px;padding:6px 10px;font-size:10px;font-weight:700;}}
        QLabel#muted {{color:{c['muted']};font-size:12px;}} QLabel#accentLabel {{color:{c['link']};font-weight:600;font-size:12px;}}
        QLabel#cardTitle {{font-size:17px;font-weight:600;}} QLabel#statValue {{font-size:26px;font-weight:700;}}
        QLabel#pageTitle {{font-size:30px;font-weight:750;}} QLabel#activeTitle {{font-size:17px;font-weight:600;padding:4px;}}
        QLabel#miniClock {{font-family:Consolas;font-size:51px;font-weight:700;}} QLabel#notice {{background:{c['soft']};padding:12px 18px;border-radius:10px;}}
        QPushButton {{background:{c['field']};border:1px solid transparent;border-radius:10px;padding:10px 13px;font-weight:600;}}
        QPushButton:hover,QPushButton:focus {{border-color:{c['accent']};}} QPushButton:pressed {{background:{c['soft']};}}
        QPushButton:disabled {{color:{c['muted']};background:{c['field']};}}
        QPushButton#primary {{background:{c['accent']};color:{c['ink']};font-weight:700;}}
        QPushButton#primary:disabled {{background:{c['border']};color:{c['muted']};}}
        QPushButton#purple {{background:#9457eb;color:white;}} QPushButton#purple:disabled {{background:{c['border']};color:{c['muted']};}}
        QPushButton#nav {{background:transparent;font-weight:500;padding:10px 15px;}}
        QPushButton#nav:checked,QPushButton#mode:checked {{background:{c['soft']};border-color:{c['accent']};}}
        QPushButton#mode {{padding:12px 20px;border-radius:20px;}} QPushButton#small {{padding:7px 9px;font-size:11px;}}
        QPushButton#preset {{padding:7px 12px;border-radius:12px;font-size:11px;}}
        QLineEdit,QComboBox,QSpinBox,QDateEdit,QDateTimeEdit {{background:{c['field']};border:1px solid {c['border']};border-radius:8px;padding:9px;selection-background-color:{c['accent']};selection-color:{c['ink']};}}
        QComboBox QAbstractItemView {{background:{c['card']};selection-background-color:{c['soft']};}}
        QProgressBar {{background:{c['border']};border:0;border-radius:4px;max-height:8px;min-height:8px;}}
        QProgressBar::chunk {{background:{c['accent']};border-radius:4px;}}
        QCheckBox {{background:transparent;spacing:8px;}} QCheckBox::indicator {{width:17px;height:17px;border:1px solid {c['muted']};border-radius:4px;background:{c['field']};}}
        QCheckBox::indicator:checked {{background:{c['accent']};border-color:{c['accent']};image:url("{check}");}}
        QListWidget#tasks {{background:transparent;border:0;outline:none;}} QListWidget::item {{border-radius:10px;margin:3px 0;background:{c['field']};}}
        QListWidget::item:selected {{background:{c['soft']};border:1px solid {c['accent']};}}
        QTableWidget {{background:{c['card']};alternate-background-color:{c['field']};border:1px solid {c['border']};border-radius:12px;selection-background-color:{c['soft']};selection-color:{c['text']};}}
        QHeaderView::section {{background:{c['field']};padding:12px;border:0;color:{c['muted']};font-size:11px;}}
        QScrollArea {{border:0;}} QScrollBar:vertical {{background:transparent;width:9px;}} QScrollBar::handle:vertical {{background:{c['border']};border-radius:4px;min-height:24px;}}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
        QWidget#mini {{background:{c['card']};border:1px solid {c['accent']};border-radius:15px;}}
        QMenu {{background:{c['card']};border:1px solid {c['border']};padding:6px;}} QMenu::item {{padding:9px 24px;}} QMenu::item:selected {{background:{c['soft']};}}
        QToolTip {{background:{c['card']};color:{c['text']};border:1px solid {c['border']};}}
        ''')
        for w in (self.ring,self.trend,self.donut,self.heat):w.update()
        pix=QPixmap(64,64); pix.fill(Qt.transparent); p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing); p.setPen(QPen(QColor(c['accent']),6)); p.drawEllipse(8,8,48,48); p.drawLine(32,17,32,32); p.drawLine(32,32,43,38); p.end(); self.setWindowIcon(QIcon(pix))
    def change_page(self,index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        if hasattr(self,'history_hint'):self.refresh_all()
    def notify(self,text):self.banner.setText(text); self.banner.show()
    def error(self,text):QMessageBox.warning(self,'Odak',str(text))
    def ask(self,text):return QMessageBox.question(self,'Odak',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
    def selected_task(self):return self.store.task(self.selected_id)
    def selected_minutes(self):
        task=self.selected_task(); return task['minutes'] if task else 30
    def selected_title(self):
        task=self.selected_task(); return task['title'] if task else 'Bir görev seç'
    def refresh_categories(self):
        self.categories={r['name']:r['id'] for r in self.store.categories()}; current=self.dash_category.currentData(); self.dash_category.blockSignals(True); self.dash_category.clear(); self.dash_category.addItem('Tüm konular',None)
        for name,cid in self.categories.items():self.dash_category.addItem(name,cid)
        self.dash_category.setCurrentIndex(max(0,self.dash_category.findData(current))); self.dash_category.blockSignals(False); self.category_names.setText('  •  '.join(self.categories) or 'Henüz ana başlık yok. İlk başlığını ekleyebilirsin.')
    def refresh_tasks(self):
        if self.closing:return
        self.tasks.blockSignals(True); self.tasks.clear(); rows=self.store.tasks(); current=None
        for task in rows:
            item=QListWidgetItem(); item.setData(Qt.UserRole,task['id']); item.setSizeHint(QSize(100,75)); self.tasks.addItem(item)
            row=QWidget(); row.setStyleSheet('background:transparent;'); box=QHBoxLayout(row); box.setContentsMargins(10,10,8,10); box.setSpacing(8)
            check=QCheckBox(); check.setChecked(bool(task['done'])); check.setToolTip('Görevin tamamını bitirdim'); check.toggled.connect(lambda v,tid=task['id']:self.mark_task(tid,v)); box.addWidget(check); texts=QVBoxLayout(); texts.setSpacing(4)
            title=label(task['title']); title.setAttribute(Qt.WA_TransparentForMouseEvents); text_width=max(55,self.tasks.viewport().width()-112); title.setMaximumWidth(text_width); title.setText(title.fontMetrics().elidedText(task['title'],Qt.ElideRight,text_width)); row.setToolTip(task['title'])
            if task['done']:font=title.font(); font.setStrikeOut(True); title.setFont(font)
            texts.addWidget(title); detail=f"{task['name']} • {task['minutes']} dk • {task['rounds']}/{task['target']} tur"; sub=label(detail,'muted'); sub.setMaximumWidth(text_width); sub.setText(sub.fontMetrics().elidedText(detail,Qt.ElideRight,text_width)); sub.setToolTip(detail); sub.setAttribute(Qt.WA_TransparentForMouseEvents); texts.addWidget(sub); box.addLayout(texts,1)
            delete=button('Sil',lambda checked=False,t=dict(task):self.archive_task(t),'small','Görevi listeden sil; çalışma geçmişini koru'); delete.setObjectName('deleteTask'); delete.setFixedWidth(40); delete.setStyleSheet('padding:6px 3px;font-size:11px;'); box.addWidget(delete); self.tasks.setItemWidget(item,row)
            if task['id']==self.selected_id:current=item
        if current:self.tasks.setCurrentItem(current)
        self.tasks.blockSignals(False); self.task_summary.setText(f"{sum(not t['done'] for t in rows)} bekleyen / {sum(bool(t['done']) for t in rows)} tamamlanan" if rows else 'İlk çalışma planın için Görev ekle’ye bas.')
        self.task_summary.setWordWrap(True)
    def task_selected(self,current,previous):
        if not current:return
        tid=current.data(Qt.UserRole)
        if self.engine.timer and self.engine.mode in ('work','overtime') and tid!=self.engine.task_id:
            self.notify('Aktif çalışmanın görevi değişmez. Bitirdikten sonra başka bir görev seçebilirsin.'); self.refresh_tasks(); return
        self.selected_id=tid; task=self.selected_task()
        if task:self.work_minutes.blockSignals(True); self.work_minutes.setValue(task['minutes']); self.work_minutes.blockSignals(False)
        self.sync_timer()
    def mark_task(self,tid,done):
        self.store.update_task(tid,done=done)
        if self.selected_id==tid and done and not self.engine.timer:self.selected_id=None
        QTimer.singleShot(0,self.refresh_all)
    def task_dialog(self,checked=False,task=None):
        d=QDialog(self); d.setWindowTitle('Görevi düzenle' if task else 'Yeni görev'); d.setMinimumWidth(470); root=QVBoxLayout(d); root.setContentsMargins(24,24,24,24); root.setSpacing(18); root.addWidget(label('Ne üzerinde çalışacaksın?','cardTitle')); form=QFormLayout(); form.setSpacing(14)
        title=QLineEdit(task['title'] if task else ''); title.setMaxLength(200); title.setPlaceholderText('Üzerinde çalışacağın konu'); cat=QComboBox()
        for name,cid in self.categories.items():cat.addItem(name,cid)
        if task:cat.setCurrentIndex(cat.findData(task['category']))
        minutes=spin(task['minutes'] if task else 30); count=spin(task['target'] if task else 1,99,' Pomodoro'); count.setObjectName('targetCount')
        def new_category():
            cid=self.add_category()
            if cid is not None:
                cat.clear()
                for name,key in self.categories.items():cat.addItem(name,key)
                cat.setCurrentIndex(cat.findData(cid))
        category_row=QHBoxLayout(); category_row.addWidget(cat,1); category_row.addWidget(button('+ Ekle',new_category,'small','Yeni ana başlık oluştur'))
        form.addRow('Görev açıklaması',title); form.addRow('Ana başlık',category_row); form.addRow('Bir Pomodoro',minutes); form.addRow('Kaç Pomodoro?',count); root.addLayout(form)
        with_breaks=QCheckBox('Tahmine aradaki molaları dahil et'); with_breaks.setChecked(True); root.addWidget(with_breaks)
        eta=label('','accentLabel',True); eta.setObjectName('estimate'); root.addWidget(eta)
        def estimate():
            seconds=planned_seconds(minutes.value(),count.value(),self.engine.cycles,self.store.get('break',5),self.store.get('long_break',15),self.store.get('long_every',4),with_breaks.isChecked())
            end=datetime.now()+timedelta(seconds=seconds)
            eta.setText(f"Şimdi başlarsan tahmini bitiş: {end:%d.%m %H:%M}\n{count.value()} × {minutes.value()} dk çalışma • Toplam {duration(seconds)}"+(' (molalar dahil)' if with_breaks.isChecked() else ' (molasız)'))
        minutes.valueChanged.connect(estimate); count.valueChanged.connect(estimate); with_breaks.toggled.connect(estimate)
        eta_timer=QTimer(d); eta_timer.timeout.connect(estimate); eta_timer.start(1000); estimate()
        root.addWidget(label('Bu bir plandır. Duraklatma ve uzatma bitiş saatini değiştirir. Hedefin üstünde de çalışabilirsin.','muted',True)); buttons=self.dialog_buttons(d); root.addWidget(buttons)
        def save():
            try:
                tid=self.store.save_task(title.text(),cat.currentData(),minutes.value(),task['id'] if task else None,target=count.value())
                if not self.engine.timer:self.selected_id=tid
                d.accept(); self.refresh_all()
            except (ValueError,sqlite3.Error) as ex:self.error(ex)
        buttons.accepted.connect(save); title.setFocus(); d.exec(); eta_timer.stop()
    def dialog_buttons(self,d):
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.button(QDialogButtonBox.Save).setText('Kaydet'); b.button(QDialogButtonBox.Cancel).setText('Vazgeç'); b.rejected.connect(d.reject); return b
    def edit_task(self):
        task=self.selected_task()
        if not task:self.notify('Düzenlemek için listeden bir görev seç.'); return
        if self.engine.timer and self.engine.task_id==task['id']:self.notify('Bu görevi oturum bittikten sonra düzenleyebilirsin.'); return
        self.task_dialog(task=task)
    def task_menu(self):
        task=self.selected_task()
        if not task:self.notify('Önce listeden bir görev seç.'); return
        menu=QMenu(self); menu.addAction('Görevi düzenle',self.edit_task); menu.addAction('Tekrar yapılacaklara al' if task['done'] else 'Tamamlandı işaretle',lambda:self.mark_task(task['id'],not task['done'])); menu.addAction('Listeden kaldır',lambda:self.archive_task(task)); menu.exec(self.tasks.mapToGlobal(self.tasks.rect().center()))
    def archive_task(self,task):
        if self.engine.timer and self.engine.task_id==task['id']:self.notify('Önce aktif oturumu bitir.'); return
        if self.ask('Görev listeden kaldırılsın mı? Geçmiş çalışma kayıtları korunur.'):
            self.store.update_task(task['id'],archived=True)
            if self.selected_id==task['id']:self.selected_id=None
            self.refresh_all()
    def reset_tasks(self):
        if self.ask('Görev adları ve hedefleri kalacak; işaretler ve görev tur sayaçları sıfırlanacak. Çalışma geçmişin korunacak. Devam edilsin mi?'):
            self.store.reset_tasks(); self.refresh_all(); self.notify('Görev ilerlemeleri sıfırlandı. Çalışma geçmişin korundu.')
    def set_daily_reset(self,value):
        self.store.set('daily_reset',value)
        if value:self.store.ensure_task_day()
        self.refresh_all()
    def duration_changed(self,n):
        task=self.selected_task()
        if task and not self.engine.timer:self.store.save_task(task['title'],task['category'],n,task['id']); self.refresh_tasks(); self.sync_timer()
    def toggle_timer(self):
        try:
            if self.engine.timer:self.engine.pause_resume()
            else:
                task=self.selected_task()
                if not task:self.notify('Önce görev ekle, listeden seç ve Başlat’a bas.'); return
                if task['done']:self.notify('Görevi tekrar çalışmak için kutucuğun işaretini kaldır.'); return
                self.engine.start_work(task); self.banner.hide()
            self.sync_timer()
        except (ValueError,sqlite3.Error) as ex:self.error(ex)
    def select_mode(self,mode):
        if self.engine.timer:
            if mode!=self.engine.mode:self.notify('Mod değiştirmek için önce Bitir’e bas. Çalıştıysan geçen süre kaydedilir.')
            self.sync_timer(); return
        if mode!='work':self.engine.start_break(mode=='long')
        self.sync_timer()
    def finish_early(self):
        if not self.engine.timer:return
        text='Uzatmayı aynı Pomodoro’ya ekleyip bitirelim mi?' if self.engine.mode=='overtime' else 'Bir Pomodoro olarak sayılsın ve gerçekten geçen süre kaydedilsin mi?' if self.engine.mode=='work' else 'Mola bitirilsin mi?'
        self.confirm_timer_action(text,False)
    def cancel_timer(self):
        if self.engine.timer:
            text='Uzatılan kısmı kaydetmeden yeni Pomodoro başlatılsın mı? Daha önce tamamlanan ana süre korunur.' if self.engine.mode=='overtime' else 'Geçen süre kaydedilmeden sayaç sıfırlanıp aynı süreyle yeniden başlasın mı?'
            self.confirm_timer_action(text,True)
    def confirm_timer_action(self,text,cancel):
        # Modal dialogs run a nested event loop: freeze the shared timer first.
        self.timer.stop(); was_running=self.engine.timer.anchor is not None
        self.engine._advance(); self.engine.timer.anchor=None; self.engine.checkpoint(); self.sync_timer()
        try:
            if self.ask(text):
                if cancel:self.engine.restart(); self.notify('Sayaç sıfırlandı ve yeniden başladı. Sıfırlanan süre eklenmedi.')
                else:self.process_event(self.engine.finish())
            elif was_running and self.engine.timer:self.engine.timer.resume()
            self.refresh_all()
        finally:self.timer.start(200)
    def time_text(self):
        t=self.engine.timer; n=int(t.elapsed) if t and self.engine.mode=='overtime' else math.ceil(max(0,t.total-t.elapsed)) if t else self.selected_minutes()*60; return f'{n//60:02d}:{n%60:02d}'
    def continue_work(self):
        try:
            self.engine.continue_work(); self.selected_id=self.engine.task_id; self.refresh_all()
            self.notify('Mor sayaçta uzatma başladı. Mola sırasında geçen süre eklenmez; Bitir toplamı aynı Pomodoro’ya yazar.')
        except (ValueError,sqlite3.Error) as ex:self.error(ex)
    def update_eta(self):
        task=self.selected_task(); e=self.engine
        if not task:self.eta_label.setText(''); return
        remaining=max(0,task['target']-task['rounds'])
        if e.mode=='overtime':self.eta_label.setText('Uzatma açık • Bitiş saatini sen belirlersin.'); return
        if not remaining:self.eta_label.setText(f"Plan tamamlandı: {task['rounds']}/{task['target']} Pomodoro"); return
        seconds=planned_seconds(task['minutes'],remaining,e.cycles,self.store.get('break',5),self.store.get('long_break',15),self.store.get('long_every',4))
        if e.timer and e.task_id==task['id']:
            if e.mode=='work':seconds=max(0,seconds-e.timer.elapsed)
            else:seconds+=e.timer.total-e.timer.elapsed
        end=datetime.now()+timedelta(seconds=seconds)
        self.eta_label.setText(f"{remaining} Pomodoro kaldı • Tahmini bitiş {end:%d.%m %H:%M}\nMolalar dahil; duraklatma / uzatmayla değişir.")
    def toggle_text(self):return ('Ⅱ Duraklat' if self.engine.timer.anchor is not None else '▶ Devam et') if self.engine.timer else '▶ Başlat'
    def sync_timer(self):
        e=self.engine; task=self.selected_task(); active=e.timer is not None; self.start_button.setText(self.toggle_text()); self.start_button.setEnabled(active or bool(task and not task['done'])); self.finish_button.setEnabled(active); self.cancel_button.setEnabled(active); self.work_minutes.setEnabled(not active and bool(task))
        if not active and task:self.work_minutes.blockSignals(True); self.work_minutes.setValue(task['minutes']); self.work_minutes.blockSignals(False)
        for b in self.presets:b.setEnabled(not active and bool(task))
        for mode,b in self.mode_buttons:b.setChecked(mode==e.mode or (mode=='work' and e.mode=='overtime'))
        self.status.setText('● '+('UZATMA' if e.mode=='overtime' else 'MOLA' if active and e.mode!='work' else 'ODAK' if active else 'HAZIR')+(' • DURAKLATILDI' if active and e.timer.anchor is None else '')); self.active_title.setText(e.work['title'] if e.work else ('Mola zamanı' if active else self.selected_title()))
        cat=next((name for name,cid in self.categories.items() if e.work and cid==e.work['category']),None); self.active_category.setText(cat or ('Biraz uzaklaş, gözlerini dinlendir.' if active and e.mode!='work' else task['name'] if task else 'Soldan görev ekle ve seç.'))
        every=self.store.get('long_every',4); is_long=(e.cycles+1)%every==0; mins=self.store.get('long_break',15) if is_long else self.store.get('break',5)
        self.next_phase.setText('Bitir: uzatmayı aynı Pomodoro’ya ekle.' if e.mode=='overtime' else 'Mola bitince yeni çalışmayı Başlat ile başlat.' if active and e.mode!='work' else f"Sıradaki: {'uzun' if is_long else 'kısa'} mola • {mins} dakika"); self.cycle_label.setText('● '*(e.cycles%every)+'○ '*(every-e.cycles%every)+f'  {e.cycles%every} / {every} tur'); self.ring.update()
        self.ring.setAccessibleName(f'{self.status.text()} • {self.time_text()}')
        self.continue_button.setVisible(e.can_continue()); self.update_eta()
        if self.widget:self.widget.sync()
    def tick(self):
        try:
            if self.store.ensure_task_day():self.refresh_all(); self.notify('Yeni gün: görev işaretleri ve tur sayaçları sıfırlandı. Geçmişin korundu.')
            event=self.engine.tick()
            if event:self.process_event(event); self.refresh_all()
            self.sync_timer()
        except (sqlite3.Error,OSError) as ex:
            if self.engine.timer:self.engine.timer.anchor=None
            self.timer.stop(); self.error('Kayıt yapılamadı; sayaç durduruldu. Disk alanını kontrol et.\n'+str(ex))
    def process_event(self,event):
        if event=='work_done':self.play_alarm(); self.notify('Pomodoro kaydedildi. '+('Mola başladı. ' if self.store.get('auto_break',True) else 'Molan hazır. ')+'Çalışmaya devam etmek için mor Devam ettir düğmesine bas.')
        elif event=='break_done':self.play_alarm(); self.notify('Mola bitti. Hazır olduğunda görevini seçip Başlat’a bas.')
        elif event=='saved':self.notify('1 Pomodoro ve gerçekten çalıştığın süre kaydedildi.')
        elif event=='extended':self.notify('Uzatma aynı Pomodoro’ya eklendi. Toplam süre güncellendi; ikinci kez sayılmadı.')
    def play_alarm(self,force=False):
        if not force and not self.store.get('sound',True):return
        if sys.platform=='win32':
            try:
                import winsound
                winsound.PlaySound(str(Path(__file__).parent/'alarm.wav'),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            except (RuntimeError,OSError):QApplication.beep()
        else:QApplication.beep()
    def refresh_all(self):
        if self.refreshing or self.closing:return
        self.refreshing=True
        try:
            self.refresh_tasks(); self.refresh_dashboard(); self.refresh_history(); today=date.today().isoformat(); rows=self.store.rows(today,today); total=sum(r['period_seconds'] for r in rows); goal=self.store.get('goal',120)*60; self.goal_text.setText(duration(total)); self.goal_bar.setValue(min(100,int(total/goal*100))); self.goal_hint.setText(f'Hedef: {duration(goal)} • %{int(total/goal*100)} tamamlandı')
            days={r['day'] for r in self.store.daily('1970-01-01',today)}; cursor=date.today(); streak=0
            if cursor.isoformat() not in days:cursor-=timedelta(days=1)
            while cursor.isoformat() in days:streak+=1; cursor-=timedelta(days=1)
            values=[duration(total),str(len(rows)),f'{streak} gün',str(sum(not t['done'] for t in self.store.tasks()))]
            for l,v in zip(self.focus_stats,values):l.setText(v)
            self.break_info.setText(f"Kısa mola: {self.store.get('break',5)} dk\nUzun mola: {self.store.get('long_break',15)} dk\nHer {self.store.get('long_every',4)} Pomodoro’da uzun mola."); self.sync_timer()
        finally:self.refreshing=False
    def bounds(self):
        today=date.today(); start={'Bugün':today,'Son 7 gün':today-timedelta(days=6),'Son 30 gün':today-timedelta(days=29),'Bu ay':today.replace(day=1),'Tüm zamanlar':date(1970,1,1)}[self.period.currentText()]; return start,today
    def refresh_dashboard(self,*args):
        if not hasattr(self,'heat'):return
        start,end=self.bounds(); cid=self.dash_category.currentData(); rows=self.store.rows(start.isoformat(),end.isoformat(),cid); total=sum(r['period_seconds'] for r in rows); daily=self.store.daily(start.isoformat(),end.isoformat(),cid); avg_start=date.fromisoformat(daily[0]['day']) if self.period.currentText()=='Tüm zamanlar' and daily else start
        values=[duration(total),str(len(rows)),str(len(daily)),duration(total/max(1,(end-avg_start).days+1))]
        for l,v in zip(self.dash_stats,values):l.setText(v)
        graph_start=max(start,end-timedelta(days=29)); byday={r['day']:r['seconds'] for r in daily}; self.trend.data=[(graph_start+timedelta(days=i),byday.get((graph_start+timedelta(days=i)).isoformat(),0)/3600) for i in range((end-graph_start).days+1)]; self.trend.update(); self.trend_hint.setText('Saat • Kesikli çizgi genel günlük hedefindir.'+(' Grafik son 30 günü gösterir.' if self.period.currentText()=='Tüm zamanlar' else ''))
        totals={}
        for r in rows:totals[r['name']]=totals.get(r['name'],0)+r['period_seconds']
        ordered=sorted(totals.items(),key=lambda x:-x[1]); self.donut.data=ordered[:5]+([('Diğer',sum(v for _,v in ordered[5:]))] if len(ordered)>5 else []); self.donut.update(); self.fill_table(self.category_table,[(n,duration(v),f'%{v/total*100:.1f}') for n,v in ordered]); self.heat.data=[(r['day'],r['seconds']) for r in self.store.daily((end-timedelta(days=56)).isoformat(),end.isoformat(),cid)]; self.heat.update()
    def refresh_history(self,*args):
        if not hasattr(self,'history_hint'):return
        start=self.from_date.date().toString('yyyy-MM-dd'); end=self.to_date.date().toString('yyyy-MM-dd')
        if start>end:self.history_rows=[]; self.fill_table(self.history,[]); self.history_hint.setText('Başlangıç tarihi bitişten sonra olamaz.'); return
        query=self.search.text().casefold().strip(); self.history_rows=[r for r in self.store.rows(start,end) if query in (r['title']+' '+r['name']).casefold()]; self.fill_table(self.history,[(r['started'].replace('T',' ')[:16],r['title'],r['name'],duration(r['period_seconds']),r['status']) for r in self.history_rows]); self.history_hint.setText(f"{len(self.history_rows)} oturum • {duration(sum(r['period_seconds'] for r in self.history_rows))} • Süreler seçilen günlere aittir.")
    def all_history(self):self.from_date.setDate(QDate(1970,1,1)); self.to_date.setDate(QDate.currentDate()); self.refresh_history()
    def delete_record(self):
        row=self.history.currentRow()
        if row<0:self.notify('Silmek için geçmişten bir kayıt seç.'); return
        session_id=self.history_rows[row]['id']
        if self.engine.work and self.engine.work['id']==session_id:self.notify('Uzatması devam eden kaydı önce Bitir ile kapat.'); return
        if self.ask('Bu çalışma kaydı kalıcı olarak silinsin mi?'):self.store.delete(session_id); self.refresh_all()
    def manual_dialog(self):
        if not self.categories:
            self.add_category()
            if not self.categories:return
        d=QDialog(self); d.setWindowTitle('Geçmiş çalışma ekle'); d.setMinimumWidth(470); root=QVBoxLayout(d); root.setContentsMargins(24,24,24,24); form=QFormLayout(); form.setSpacing(14); title=QLineEdit(); title.setMaxLength(200); cat=QComboBox()
        for name,cid in self.categories.items():cat.addItem(name,cid)
        start=QDateTimeEdit(QDateTime.currentDateTime().addSecs(-1800)); start.setDisplayFormat('dd.MM.yyyy HH:mm'); start.setCalendarPopup(True); minutes=spin(30)
        for name,field in [('Açıklama',title),('Ana başlık',cat),('Başlangıç',start),('Çalışılan süre',minutes)]:form.addRow(name,field)
        root.addLayout(form); buttons=self.dialog_buttons(d); root.addWidget(buttons)
        def save():
            if not title.text().strip():self.error('Bir açıklama yaz.'); return
            dt=start.dateTime().toPython(); end=dt+timedelta(minutes=minutes.value())
            if end>datetime.now():self.error('Çalışmanın bitiş zamanı gelecekte olamaz.'); return
            try:
                r=record(title.text(),cat.currentData(),dt,minutes.value()); r['seconds']=minutes.value()*60; r['status']='Elle eklendi'; allocate(r['days'],end,r['seconds']); self.store.save(r); d.accept(); self.refresh_all()
            except (ValueError,sqlite3.Error) as ex:self.error(ex)
        buttons.accepted.connect(save); d.exec()
    def export(self):
        self.refresh_history(); path,_=QFileDialog.getSaveFileName(self,'CSV kaydet','odak_calismalar.csv','CSV (*.csv)')
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f,delimiter=';'); writer.writerow(['Başlangıç','Açıklama','Ana başlık','Seçili günlerde dakika','Toplam dakika','Durum'])
                def safe(v):return "'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v
                for r in self.history_rows:writer.writerow([safe(r['started']),safe(r['title']),safe(r['name']),round(r['period_seconds']/60,2),round(r['seconds']/60,2),r['status']])
            self.notify('Görüntülenen kayıtlar CSV olarak kaydedildi.')
        except OSError as ex:self.error(ex)
    def add_category(self):
        name,ok=QInputDialog.getText(self,'Ana başlık ekle','Çalışmalarını gruplamak için bir başlık yaz:')
        if ok:
            try:
                self.store.add_category(name); self.refresh_categories(); self.refresh_all()
                return self.categories[name.strip()]
            except (ValueError,sqlite3.Error) as ex:self.error(ex)
    def save_settings(self):
        for key,value in [('goal',self.goal_input.value()),('break',self.short_input.value()),('long_break',self.long_input.value()),('long_every',self.every_input.value())]:self.store.set(key,value)
        self.refresh_all(); self.notify('Ayarlar kaydedildi. Süre değişiklikleri sonraki oturumlara uygulanır.')
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,'Veritabanını yedekle',f'odak_yedek_{date.today()}.sqlite3','SQLite (*.sqlite3)')
        if not path:return
        if Path(path).resolve()==self.data_path.resolve():self.error('Asıl veritabanından farklı bir dosya seç.'); return
        try:
            db=sqlite3.connect(path)
            try:self.store.db.backup(db)
            finally:db.close()
            self.notify('Kayıtlar, görevler ve ayarlar yedeklendi.')
        except sqlite3.Error as ex:self.error(ex)
    def show_widget(self):
        if self.widget is None:self.widget=MiniWidget(self)
        self.widget.sync(); self.widget.show(); self.widget.raise_()
    def minimize_to_widget(self):self.show_widget(); self.hide()
    def set_widget_top(self,value):
        self.store.set('widget_top',value)
        if self.widget:
            visible=self.widget.isVisible(); self.widget.setWindowFlag(Qt.WindowStaysOnTopHint,value)
            if visible:self.widget.show()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'widget_help'):return
        compact=self.height()<880
        if compact!=self.compact:
            self.compact=compact
            for w in (self.focus_tip,self.phase_intro,self.sound_help,self.widget_help,*self.presets):w.setVisible(not compact)
            self.tasks.setMinimumHeight(130 if compact else 240)
            self.ring.setMinimumSize(230 if compact else 295,200 if compact else 310)
            self.ring.setMaximumHeight(230 if compact else 16777215)
            self.focus_grid.setAlignment(self.timer_card,Qt.AlignTop if compact else Qt.Alignment())
            self.center_layout.setSpacing(8 if compact else 14)
            self.center_layout.setContentsMargins(16 if compact else 20,14 if compact else 20,16 if compact else 20,14 if compact else 20)
        QTimer.singleShot(0,self.refresh_tasks)
    def closeEvent(self,event):
        try:self.engine.close()
        except (sqlite3.Error,OSError) as ex:self.error('İlerleme kaydedilemedi. Uygulama açık bırakıldı.\n'+str(ex)); event.ignore(); return
        self.closing=True; self.timer.stop()
        if self.widget:self.widget.close()
        self.store.db.close(); event.accept()

def data_directory():
    path=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'OdakPomodoro'; path.mkdir(parents=True,exist_ok=True); return path

def main():
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName('OdakPomodoro'); app.setApplicationVersion('2.2.0')
    try:return run_application(app)
    except (OSError,sqlite3.Error,ValueError) as ex:
        QMessageBox.critical(None,'Odak açılamadı','Veri dosyası açılamadı. Disk alanını ve klasör izinlerini kontrol et.\nVar olan veritabanını silmeden önce yedeğini al.\n\n'+str(ex))
        return 1

def run_application(app):
    lock=open(data_directory()/'app.lock','a+b'); lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:QMessageBox.information(None,'Odak açık','Uygulama zaten açık. Eski sürümü veya widget’ı kontrol et.'); return 0
    try:
        window=MainWindow(); window.show(); return app.exec()
    finally:lock.close()
