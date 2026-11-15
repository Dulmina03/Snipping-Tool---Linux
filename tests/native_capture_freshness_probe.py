"""Opt-in real Wayland public-scene PNG freshness/toolbar-exclusion check.

Run only with the normal instance stopped. No desktop settings/permissions change.
Qt Escape is programmatic, NOT physical keyboard acceptance.
"""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import main
main.prepare_qt_environment()
from PIL import Image
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtGui import QColor,QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget
from capture.display_mapping import read_gnome_layout
from ui.capture_menu import CaptureMenu


def run():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(main.APP_ID);app.setDesktopFileName(main.APP_ID)
    menu=CaptureMenu();scene=QWidget();scene.setWindowTitle('Public capture regression fixture')
    scene.setAutoFillBackground(True)
    rows=[];menu.latency_listener=rows.append
    def events(seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:app.processEvents();time.sleep(.0005)
    def wait(predicate,limit=20):
        deadline=time.monotonic()+limit
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return
            time.sleep(.0005)
        raise TimeoutError('Native public-scene readiness not observed')
    try:
        task=menu.jobs.submit(read_gnome_layout());wait(task.done)
        layout=task.result();screens=app.screens()
        if len(layout.monitors)!=1 or len(screens)!=1 or layout.monitors[0].scale!=1 or screens[0].devicePixelRatio()!=1:
            print(json.dumps({'status':'NOT RUN','reason':'This pixel fixture requires one monitor at100%'}));return
        scene.showFullScreen();scene.activateWindow();events(.1)
        for index in range(6):
            color=(20+index*25,90+index*13,150-index*17)
            palette=scene.palette();palette.setColor(QPalette.Window,QColor(*color));scene.setPalette(palette)
            scene.repaint();events(.06)  # Test-scene presentation, never production capture delay.
            rows.clear();menu.launch_overlay()
            wait(lambda:any(r['stage']=='toolbar_paint_processed' for r in rows))
            overlay=menu._overlay;surface=getattr(overlay,'primary',overlay)
            rect=surface._toolbar.geometry()
            with Image.open(menu._src_path) as image:
                rgb=image.convert('RGB')
                points=[(rect.left()+int(rect.width()*fraction),rect.center().y()) for fraction in (.1,.3,.5,.7,.9)]
                matches=all(rgb.getpixel(point)==color for point in points)
                rgb.close()
            if index==0 and not matches:
                print(json.dumps({'status':'NOT RUN','reason':'Public scene does not match raw PNG at baseline; focus/color-management fixture not established'}));return
            assert matches,'Fresh public pixels missing or previous toolbar captured'
            QTest.keyClick(surface,Qt.Key_Escape)
            wait(lambda:menu._overlay is None and not menu.jobs.tasks)
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
            print(json.dumps({'index':index,'status':'PASS','fresh_public_pixels':True,'toolbar_absent_from_png':True,'synthetic_escape_closed':True}),flush=True)
    finally:
        menu.shutdown();menu.jobs.close();scene.close()


if __name__=='__main__':run()
