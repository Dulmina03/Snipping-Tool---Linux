"""Opt-in GNOME native production-handler probe. Public fixtures; clipboard overwritten.

Portal backdrop is a deterministic fixture; production overlay/result/OCR/clipboard
handlers run unchanged. Separate native Qt reader compares bytes/pixels and paste.
Not a physical keyboard/mouse test. Run .venv/bin/python tests/production_clipboard_probe.py.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from unittest.mock import AsyncMock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import main
main.prepare_qt_environment()
from PySide6.QtCore import QTimer,QPoint,Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PIL import Image,ImageDraw,ImageFont
from PIL.PngImagePlugin import PngInfo
from clipboard_native_probe import ClipboardEditor

MIXED='English punctuation: hello, world! සිංහල ශ්‍රී ලංකාව — ආයුබෝවන්.\nZWJ: \u200d'
ENGLISH='Offline English screenshot test 123.'


def reader(reference):
    expected=json.loads(Path(reference).read_text())
    app=QApplication([]);editor=ClipboardEditor();editor.resize(700,300);editor.show();editor.activateWindow()
    count=0
    def poll():
        nonlocal count
        count+=1
        result={'reader_active':editor.isActiveWindow(),'pass':False}
        if result['reader_active']:
            mime=app.clipboard().mimeData()
            if expected['mode']=='image':
                raw=bytes(mime.data('image/png'))
                image=QImage.fromData(raw,'PNG').convertToFormat(QImage.Format_ARGB32)
                reference_image=QImage(expected['path']).convertToFormat(QImage.Format_ARGB32)
                result['png_pixels_equal']=not image.isNull() and image==reference_image
                editor.clear();editor.paste()
                result['paste_equal']='<img ' in editor.toHtml()
                result['pass']=result['png_pixels_equal'] and result['paste_equal']
            else:
                result['utf8_equal']=bytes(mime.data('text/plain;charset=utf-8'))==expected['text'].encode('utf-8')
                editor.clear();editor.paste()
                result['paste_equal']=editor.toPlainText()==expected['text']
                result['pass']=result['utf8_equal'] and result['paste_equal']
        if result['pass'] or count>=45:
            print(json.dumps(result),flush=True);app.quit()
    timer=QTimer();timer.timeout.connect(poll);timer.start(100)
    app.exec()


def writer():
    import ui.capture_menu as capture
    from ui.overlay import SnipMode
    original=main.configure_application
    ledger=[];owned={};beats=[0]
    def record(test,status,**fields):
        row={'test':test,'status':status,**fields};ledger.append(row);print(json.dumps(row),flush=True)
    async def wait_for(condition,seconds=12):
        for _ in range(int(seconds/.05)):
            if condition():return True
            await asyncio.sleep(.05)
        return False
    async def read(scratch,expected):
        target=Path(scratch)/('reference-'+uuid.uuid4().hex+'.json');target.write_text(json.dumps(expected))
        process=await asyncio.create_subprocess_exec(sys.executable,__file__,'--read',str(target),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            output,_=await asyncio.wait_for(process.communicate(),8)
            return json.loads(output)
        finally:
            if process.returncode is None:process.kill();await process.wait()
    async def run(app,menu,manager,tray,tray_menu):
        try:
            # This public OCR/reference fixture uses fixed 100%-scale positions.
            # Geometry fixtures cover other layouts; do not report a false native
            # clipboard regression if this older probe cannot represent them.
            from capture.display_mapping import read_gnome_layout
            layout = await read_gnome_layout()
            screens = QApplication.screens()
            if (len(layout.monitors) != 1 or len(screens) != 1
                    or layout.monitors[0].scale != 1 or screens[0].devicePixelRatio() != 1):
                record('fixture_layout', 'NOT RUN', reason='This clipboard probe requires one monitor at 100%; use geometry fixtures and physical checks for other layouts.')
                return
            with tempfile.TemporaryDirectory(prefix='snipping-production-') as scratch,patch.object(capture,'SCREENSHOTS_DIR',Path(scratch)/'saved'):
                for case in ('rectangle','fullscreen','rectangle_repeat','english_ocr','unicode_transfer'):
                    width,height=capture._get_virtual_size()
                    source=Path(scratch)/(case+'.png')
                    image=Image.new('RGB',(width,height),'white')
                    draw=ImageDraw.Draw(image)
                    # Fresh per-capture public pixels defeat stale clipboard matches.
                    draw.rectangle((80,400,250,500),fill='#'+uuid.uuid4().hex[:6])
                    if 'ocr' in case or case=='unicode_transfer':
                        draw.rectangle((0,300,width,700),fill='white')
                        draw.text((50,400),ENGLISH,fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',36))
                    metadata = PngInfo()
                    metadata.add_text('Software', 'gnome-screenshot')
                    image.save(source, pnginfo=metadata)  # Controlled full-stage fixture.
                    with patch.object(capture,'_portal_screenshot',new=AsyncMock(return_value=source)):
                        menu.launch_overlay()
                        if not await wait_for(lambda:menu._overlay is not None):
                            record(case,'FAIL',reason='No overlay');continue
                    overlay=menu._overlay
                    surface=getattr(overlay, 'primary', overlay)
                    await asyncio.sleep(.8)
                    if not overlay.isActiveWindow():
                        record(case,'NOT RUN',reason='Native capture surface did not receive focus');menu._on_cancelled();continue
                    before=beats[0]
                    if case=='fullscreen':
                        overlay._toolbar._buttons[SnipMode.FULLSCREEN].click()
                        await wait_for(lambda:not menu.busy,25)
                    else:
                        if 'ocr' in case or case=='unicode_transfer':
                            overlay._toolbar.action_combo.setCurrentIndex(1)
                        async def fake_text(path):
                            await asyncio.sleep(.3);return MIXED
                        context=patch.object(capture,'extract_text_async',fake_text) if case=='unicode_transfer' else patch.dict(os.environ,{})
                        with context:
                            QTest.mousePress(surface,Qt.LeftButton,Qt.NoModifier,QPoint(20,350))
                            QTest.mouseMove(surface,QPoint(min(width-20,1200),650))
                            QTest.mouseRelease(surface,Qt.LeftButton,Qt.NoModifier,QPoint(min(width-20,1200),650))
                            await wait_for(lambda:not menu.busy,25)
                    path=menu.last_capture_path
                    valid=path is not None and path.is_file()
                    if valid:
                        with Image.open(path) as saved:
                            saved.load();size=saved.size
                            expected_pixels=image if case=='fullscreen' else image.crop((20,350,min(width-20,1200)+1,651))
                            integrity=saved.size==expected_pixels.size and saved.tobytes()==expected_pixels.tobytes()
                    else:integrity=False;size=None
                    text_mode='ocr' in case or case=='unicode_transfer'
                    expected={'mode':'text','text':MIXED if case=='unicode_transfer' else ENGLISH} if text_mode else {'mode':'image','path':str(path)}
                    if menu._overlay is not None:
                        record(case,'FAIL',reason='Delivery pending or overlay not closed',ocr_returned=menu.last_extracted_text is not None);menu._on_cancelled();continue
                    result=await read(scratch,expected)
                    await asyncio.sleep(.5)
                    second=await read(scratch,expected)
                    record(case,'PASS' if integrity and result['pass'] and second['pass'] else 'FAIL',saved_integrity=integrity,size=size,first_reader=result,after_focus_change=second,event_loop_alive=beats[0]>before)
                    await asyncio.sleep(1.1)
        except Exception as error:
            record('harness','FAIL',error=type(error).__name__,detail=str(error))
        finally:
            tray_menu.actions()[-1].trigger()
    def configure(app):
        values=original(app);owned['manager']=values[1]
        timer=QTimer(values[0]);timer.timeout.connect(lambda:beats.__setitem__(0,beats[0]+1));timer.start(20)
        QTimer.singleShot(200,lambda:values[0].jobs.submit(run(app,*values)))
        QTimer.singleShot(120000,app.quit)
        return values
    with patch.object(main,'configure_application',configure):result=main.main()
    record('shutdown','PASS' if result==0 and not owned['manager']._thread.is_alive() else 'FAIL',thread_alive=owned['manager']._thread.is_alive())
    return 1 if any(r['status']=='FAIL' for r in ledger) else 0


if __name__=='__main__':
    if '--read' in sys.argv:reader(sys.argv[-1])
    else:raise SystemExit(writer())
