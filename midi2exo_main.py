import copy
import math
import mido
import os
import sys
import PyQt5
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QAction, QApplication, QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PyQt5.QtGui import QBrush, QColor, QIcon, QTextFormat
from PyQt5.Qt import Qt, QIntValidator
from PyQt5.QtCore import QEvent, QObject
from pyaviutl.exo import *

version = '1.0a'

illegalChars = dict((ord(char), None) for char in '\/*?:"<>|')
exts = ['mp4', 'ts', 'wmv', 'mov', 'mkv', 'avi']
def toFileName(s):
    return s.translate(illegalChars)

class DropFileHandler(QObject):    
    def eventFilter(self, watched, event):
        if event.type() == QEvent.DragEnter:
            event.accept()
        elif event.type() == QEvent.Drop:
            mime = event.mimeData()
            if mime.hasUrls():
                watched.setText(os.path.normpath(event.mimeData().urls()[0].toLocalFile()))
                return True
        return super().eventFilter(watched, event)
class MenuItem:
    def __init__(self, parent, name, tip=None, target=None, shortcut=None):
        self.name = name
        self.action = QAction(name, parent)
        if shortcut is not None:
            self.action.setShortcut(shortcut)
        if tip is not None:
            self.action.setStatusTip(tip)
        if target is not None:
            self.action.triggered.connect(target)
class Channel:
    def __init__(self, name, items, path, alpha, flip):
        self.items = items
        self.name = name
        self.auto = True
        self.path = path
        self.alpha = alpha
        self.flip = flip
        self.exists = False
        self.enabled = True
    def clearAuto(self):
        self.auto = False
    def size(self):
        return len(self.items)
class Note:
    def __init__(self, start=1, layer=1, objid=1):
        self.start, self.layer, self.objid = start, layer, objid

class Midi2ExoMain(QMainWindow):
    titlePref = 'midi2exo v{0}'.format(version)
    nowChl = -1
    def __init__(self):
        global app
        super().__init__()
        self.menu = {
            '文件': [
                MenuItem(self, '打开', '打开 MIDI 文件', self.open, 'Ctrl+O'),
                MenuItem(self, '导出 EXO', '导出 EXO 文件', self.save, 'Ctrl+S'),
                MenuItem(self, '|'),
                MenuItem(self, '退出', '退出本应用程序', self.close, 'Alt+F4')
            ],
            '帮助': [MenuItem(self, '关于', '关于本程序', self.about)]
        }
        self.file = ''
        self.channels = []
        self.setAcceptDrops(True)
        app.focusChanged.connect(self.onFocusChanged)
        self.render()
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if len(files) != 0:
            self.file = files[0]
            self.handleMidi()
    def about(self):
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle('关于')
        msgBox.setText('''
            <center>
                <h3>midi2exo</h3>
                <font color=grey align=left>
                    <div>版本：v{0}</div>
                    <div>作者：xszqxszq</div>
                </font>
            </center>'''.format(version))
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setInformativeText('本程序可以利用 MIDI 文件生成 exo 文件，以减轻在 AviUtl 中音乐相关剪辑（如音MAD）的工作量。')
        aboutQt = msgBox.addButton('关于 Qt', QMessageBox.ActionRole)
        msgBox.addButton(QMessageBox.Ok)
        msgBox.exec_()
        if msgBox.clickedButton() == aboutQt:
            QMessageBox.aboutQt(self, '关于 Qt')
    def open(self):
        self.file, _ = QFileDialog.getOpenFileName(self, '打开 MIDI 文件', filter='MIDI 文件 (*.mid)')
        if self.file:
            self.handleMidi()
    def setDefSrcPath(self):
        path = QFileDialog.getExistingDirectory(self, '选择素材默认存放文件夹', self.defSrcPathLE.text())
        if path != '':
            self.defSrcPathLE.setText(os.path.normpath(path))
    def setNowSrcPath(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择素材文件', self.nowSrcPathLE.text())
        if path != '':
            self.nowSrcPathLE.setText(os.path.normpath(path))
    def handleMidi(self):
        try:
            self.midi = mido.MidiFile(self.file)
        except Exception as e:
            QMessageBox.critical(self, '错误', '文件无法读取，该文件可能不是midi文件')
            return
        self.channels = []
        nowLayer, nowTempo = 0, 500000
        for track in self.midi.tracks:
            initial = True
            nowPosition = 0
            lastNote = None
            for msg in track:
                nowPosition += msg.time
                if msg.type == 'set_tempo':
                    nowTempo = msg.tempo
                elif msg.type == 'note_on':
                    if initial:
                        nowLayer += 1
                        self.channels.append(Channel(track.name, [], self.getPath(self.defSrcPathLE.text(), track.name, self.extLE.text()), self.defAlpha.checkState(), self.defFlip.checkState()))
                        initial = False
                    if lastNote and lastNote.start == nowPosition:
                        continue
                    if lastNote:
                        self.channels[lastNote.objid].items.append(ExoVideo(
                            start = mido.tick2second(lastNote.start, self.midi.ticks_per_beat, nowTempo),
                            end = mido.tick2second(nowPosition, self.midi.ticks_per_beat, nowTempo),
                            layer = lastNote.layer
                        ))
                    lastNote = Note(nowPosition, nowLayer, nowLayer-1)
            if lastNote is not None:
                self.channels[lastNote.objid].items.append(ExoVideo(
                    start = mido.tick2second(lastNote.start, self.midi.ticks_per_beat, nowTempo),
                    end = mido.tick2second(nowPosition, self.midi.ticks_per_beat, nowTempo),
                    layer = lastNote.layer
                ))
        self.nowChl = -1
        self.refresh()
        self.setWindowTitle('{0} - {1}'.format(self.titlePref, self.file))
        self.chlLstWid.clearSelection()
    def anyNonExist(self):
        for i in self.channels:
            if i.enabled and not i.exists:
                return True
        return False
    def save(self):
        self.refresh()
        if self.anyNonExist():
            reply = QMessageBox.warning(self, '警告', '有轨道的素材文件不存在，这可能导致exo文件在导入时会不断报错，是否仍要导出？', QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        path, _ = QFileDialog.getSaveFileName(self, '导出 EXO 文件', filter='EXO 文件 (*.exo)')
        if not path:
            return
        exo = {}
        exo['exedit'] = {
            'width': int(self.geomWLE.text()),
            'height': int(self.geomHLE.text()),
            'rate': int(self.fps.text()),
            'scale': 1,
            'audio_rate': int(self.sr.text()),
            'audio_ch': 2,
        }
        exo['exedit']['length'] = math.ceil(self.midi.length * exo['exedit']['rate']) # !Important: Length must be calculated
        nowObj = 0
        for ch in self.channels:
            if not ch.enabled:
                continue
            vid = SceneSettings(ch.path, alpha=ch.alpha//2)
            for v in ch.items:
                exo[nowObj] = copy.deepcopy(v)
                exo[nowObj].group = nowObj + 1
                exo[nowObj]['sceneSettings'] = vid
                exo[nowObj]['effects'][0]['左右翻转'] = ch.flip // 2 * (nowObj % 2)
                exo[nowObj]['start'], exo[nowObj]['end'] = 1 + math.ceil(v['start'] * exo['exedit']['rate']), math.ceil(v['end'] * exo['exedit']['rate'])
                nowObj += 1
            if nowObj != 0:
                exo[nowObj-1]['end'] = exo['exedit']['length']
        with open(path, 'w', encoding='GBK') as f:
            for key, value in exo.items():
                f.write('[{0}]\n'.format(key))
                if type(value) == ExoVideo:
                    attid = 1
                    for ikey, ival in value.items():
                        if ikey == 'sceneSettings':
                            f.write('[{0}.0]\n'.format(key))
                            for skey, sval in ival.items():
                                if skey == 'scene':
                                    f.write('={0}\n'.format(sval))
                                else:
                                    f.write('{0}={1}\n'.format(skey, sval))
                        elif ikey == 'effects':
                            for e in ival:
                                f.write('[{0}.{1}]\n'.format(key, attid))
                                for akey, aval in e.items():
                                    f.write('{0}={1}\n'.format(akey, aval))
                                attid += 1
                        else:
                            f.write('{0}={1}\n'.format(ikey, ival))
                else:
                    for ikey, ival in value.items():
                        f.write('{0}={1}\n'.format(ikey, ival))
        QMessageBox.information(self, '导出完毕', 'EXO 文件已成功导出。')
    def getPath(self, prvPath, prefix, default):
        global exts
        for i in [default, *exts]:
            nowPath = os.path.normpath(prvPath + '/' + toFileName(prefix + '.' + i))
            if os.path.exists(nowPath):
                return nowPath
        return os.path.normpath(prvPath + '/' + toFileName(prefix + '.' + default))
    def refresh(self):
        for i in self.channels:
            if i.auto:
                i.path = self.getPath(self.defSrcPathLE.text(), i.name, self.extLE.text())
            i.exists = os.path.exists(i.path)
        self.renderList()
    def renderList(self):
        self.chlLstWid.clear()
        for index, i in enumerate(self.channels):
            item = QTreeWidgetItem(self.chlLstWid)
            if not i.enabled:
                item.setText(0, '已禁用')
                item.setForeground(0, QBrush(QColor('#C0C0C0')))
            elif i.exists:
                item.setText(0, '正常')
                item.setForeground(0, QBrush(QColor('#009900')))
            else:
                item.setText(0, '文件不存在')
                item.setForeground(0, QBrush(Qt.red))
            item.setText(1, str(index))
            item.setText(2, i.name)
            item.setText(3, str(i.size()))
            item.setText(4, i.path)
            i.item = item
            self.chlLstWid.addTopLevelItem(item)
        for i in range(5):
            self.chlLstWid.resizeColumnToContents(i)
        self.propGrp.setEnabled(self.nowChl != -1)
    def render(self):
        # Basic window properties
        self.setWindowTitle(self.titlePref)   
        # Show status bar
        self.statusBar()
        # Show menu
        menuBar = self.menuBar()
        for name, column in self.menu.items():
            menu = menuBar.addMenu('&' + name)
            for i in column:
                if i.name == '|':
                    menu.addSeparator()
                else:
                    menu.addAction(i.action)
        # Show workspace
        prjPropGrp = QGroupBox('工程设置', self)
        prjPropGrpLyt = QVBoxLayout()
        geomLyt = QHBoxLayout()
        self.geomWLE = QLineEdit(prjPropGrp)
        self.geomHLE = QLineEdit(prjPropGrp)
        self.fps = QLineEdit(prjPropGrp)
        self.sr = QLineEdit(prjPropGrp)
        self.extLE = QLineEdit(prjPropGrp)
        self.geomWLE.setText('1920')
        self.geomHLE.setText('1080')
        self.fps.setText('60')
        self.sr.setText('48000')
        self.extLE.setText('mp4')
        self.geomWLE.setValidator(QIntValidator(1, 100000, self))
        self.geomHLE.setValidator(QIntValidator(1, 100000, self))
        self.fps.setValidator(QIntValidator(1, 10000, self))
        self.sr.setValidator(QIntValidator(0, 22579200, self))
        self.extLE.setValidator(PyQt5.Qt.QRegularExpressionValidator(PyQt5.Qt.QRegularExpression('^[a-zA-Z0-9]*$')))
        self.geomWLE.setFixedWidth(40)
        self.geomHLE.setFixedWidth(40)
        self.fps.setFixedWidth(40)
        self.sr.setFixedWidth(40)
        self.extLE.setFixedWidth(40)
        geomLyt.addWidget(QLabel('图像大小'))
        geomLyt.addWidget(self.geomWLE)
        geomLyt.addWidget(QLabel('×'))
        geomLyt.addWidget(self.geomHLE)
        geomLyt.addStretch()
        geomLyt.addWidget(QLabel('帧速率'))
        geomLyt.addWidget(self.fps)
        geomLyt.addStretch()
        geomLyt.addWidget(QLabel('音频采样率'))
        geomLyt.addWidget(self.sr)
        srcLyt = QHBoxLayout()
        srcLyt.addWidget(QLabel('首选素材扩展名'))
        srcLyt.addWidget(self.extLE)
        srcLyt.addStretch()
        defSrcSel = QHBoxLayout()
        defSrcSel.addWidget(QLabel('默认素材位置'))
        self.defSrcPathLE = QLineEdit(prjPropGrp)
        self.defSrcPathLE.setText(os.path.normpath(os.path.expanduser("~/Desktop")))
        self.defSrcPathLE.installEventFilter(DropFileHandler(self))
        defSrcSel.addWidget(self.defSrcPathLE)
        defSrcSelBtn = QPushButton('...')
        defSrcSelBtn.clicked.connect(self.setDefSrcPath)
        defSrcSel.addWidget(defSrcSelBtn)
        defChkLyt = QHBoxLayout()
        self.defAlpha = QCheckBox('默认导入Alpha通道', prjPropGrp)
        self.defFlip = QCheckBox('默认启用左右翻转', prjPropGrp)
        self.defFlip.setCheckState(2)
        defApplyBtn = QPushButton('应用')
        defApplyBtn.clicked.connect(self.apply)
        defChkLyt.addWidget(self.defAlpha)
        defChkLyt.addWidget(self.defFlip)
        defChkLyt.addStretch()
        defChkLyt.addWidget(defApplyBtn)
        prjPropGrpLyt.addLayout(defSrcSel)
        prjPropGrpLyt.addLayout(geomLyt)
        prjPropGrpLyt.addLayout(srcLyt)
        prjPropGrpLyt.addLayout(defChkLyt)
        prjPropGrp.setLayout(prjPropGrpLyt)

        lstGrp = QGroupBox('轨道列表', self)
        lstGrpLyt = QVBoxLayout()
        self.chlLstWid = QTreeWidget(self)
        self.chlLstWid.setHeaderLabels(['状态', '编号', '音轨名称', '音符数', '素材路径'])
        self.chlLstWid.setRootIsDecorated(False)
        lstGrpLyt.addWidget(self.chlLstWid)
        lstGrp.setLayout(lstGrpLyt)
        self.chlLstWid.itemClicked.connect(self.onItemClicked)

        self.propGrp = QGroupBox('轨道设置', self)
        propGrpLyt = QVBoxLayout()
        infoLyt = QHBoxLayout()
        self.nowChlLE = QLineEdit(self.propGrp)
        self.nowChlLE.setReadOnly(True)
        infoLyt.addWidget(QLabel('音轨名称'))
        infoLyt.addWidget(self.nowChlLE)
        infoLyt.addStretch()
        self.nowState = QCheckBox('启用轨道')
        self.nowState.stateChanged.connect(self.onStateChanged)
        srcSel = QHBoxLayout()
        srcSel.addWidget(QLabel('素材路径'))
        self.nowSrcPathLE = QLineEdit(self.propGrp)
        self.nowSrcPathLE.textChanged.connect(self.onPathChanged)
        self.nowSrcPathLE.installEventFilter(DropFileHandler(self))
        srcSel.addWidget(self.nowSrcPathLE)
        srcSelBtn = QPushButton('...')
        srcSelBtn.clicked.connect(self.setNowSrcPath)
        srcSel.addWidget(srcSelBtn)
        chkLyt = QHBoxLayout()
        self.nowAlpha = QCheckBox('导入Alpha通道', self.propGrp)
        self.nowAlpha.stateChanged.connect(self.onAlphaChanged)
        self.nowFlip = QCheckBox('启用左右翻转', self.propGrp)
        self.nowFlip.stateChanged.connect(self.onFlipChanged)
        chkLyt.addWidget(self.nowAlpha)
        chkLyt.addWidget(self.nowFlip)
        propGrpLyt.addLayout(infoLyt)
        propGrpLyt.addWidget(self.nowState)
        propGrpLyt.addLayout(srcSel)
        propGrpLyt.addLayout(chkLyt)
        propGrpLyt.addStretch()
        self.propGrp.setLayout(propGrpLyt)

        chlUtls = QHBoxLayout()
        chlUtls.addWidget(lstGrp)
        chlUtls.addWidget(self.propGrp)
        
        mainLyt = QVBoxLayout()
        mainLyt.addWidget(prjPropGrp)
        mainLyt.addLayout(chlUtls)
        wid = QWidget(self)
        self.setCentralWidget(wid)
        wid.setLayout(mainLyt)

        self.renderList()
        self.show()

    def apply(self):
        for i in self.channels:
            if i.auto:
                i.alpha = self.defAlpha.checkState()
                i.flip = self.defFlip.checkState()
        self.refresh()
    @QtCore.pyqtSlot()
    def onFocusChanged(self):
        self.refresh()
    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def onItemClicked(self, it, col):
        self.nowChl = int(it.text(1))
        self.propGrp.setEnabled(True)
        self.nowItem = it
        self.nowChlLE.setText(self.channels[self.nowChl].name)
        self.nowSrcPathLE.setText(self.channels[self.nowChl].path)
        self.nowAlpha.setCheckState(self.channels[self.nowChl].alpha)
        self.nowFlip.setCheckState(self.channels[self.nowChl].flip)
        self.nowState.setCheckState(self.channels[self.nowChl].enabled * 2)
    @QtCore.pyqtSlot(str)
    def onPathChanged(self, new):
        if self.nowChl == -1 or self.channels[self.nowChl].path == new:
            return
        self.channels[self.nowChl].path = new
        self.channels[self.nowChl].clearAuto()
        self.refresh()
    @QtCore.pyqtSlot(int)
    def onAlphaChanged(self, new):
        if self.nowChl == -1 or self.channels[self.nowChl].alpha == new:
            return
        self.channels[self.nowChl].alpha = new
        self.channels[self.nowChl].clearAuto()
    @QtCore.pyqtSlot(int)
    def onFlipChanged(self, new):
        if self.nowChl == -1 or self.channels[self.nowChl].flip == new:
            return
        self.channels[self.nowChl].flip = new
        self.channels[self.nowChl].clearAuto()
    @QtCore.pyqtSlot(int)
    def onStateChanged(self, new):
        if self.nowChl == -1:
            return
        self.channels[self.nowChl].enabled = new == 2
        self.refresh()
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Midi2ExoMain()
    sys.exit(app.exec_())