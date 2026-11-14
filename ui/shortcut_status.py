"""Compact main-thread presentation of portal shortcuts and identity."""
from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLayout,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)
from shortcuts.assignment import display_shortcut


class ShortcutStatusDialog(QDialog):
    """Opened only by a tray action; all sizes use Qt logical screen pixels."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Shortcut status — AI Snipping Tool')
        self.setModal(False)
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        content = QVBoxLayout(body)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content.addWidget(self.summary)
        self.details_button = QPushButton('Show details')
        self.details_button.setCheckable(True)
        content.addWidget(self.details_button)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QTextEdit.WidgetWidth)
        self.details.setMinimumWidth(0)
        self.details.setFixedHeight(130)
        self.details.hide()
        self.details_button.toggled.connect(self._toggle_details)
        content.addWidget(self.details)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self.resize(460, 290)

    def _toggle_details(self, visible):
        self.details.setVisible(visible)
        self.details_button.setText('Hide details' if visible else 'Show details')

    def fit_to_screen(self, available=None):
        available = available or self.screen().availableGeometry()
        # Includes margins for compositor decorations; never multiply by DPR.
        self.setMaximumSize(max(1, available.width() - 32), max(1, available.height() - 48))
        self.resize(min(460, self.maximumWidth()), min(340, self.maximumHeight()))


class ShortcutStatus(QObject):
    def __init__(self, menu, manager, tray, capture_action, status_action,
                 identity_action, configure_action):
        super().__init__(menu)
        self.menu, self.manager, self.tray = menu, manager, tray
        self.capture_action, self.status_action = capture_action, status_action
        self.identity_action, self.configure_action = identity_action, configure_action
        self.requested = manager.preferred_trigger
        self.actual = 'Waiting for desktop assignment'
        self.registration = 'Waiting for desktop'
        self.assignment_text = ''
        self.identity_text = 'Checking'
        self.identity_detail = ''
        self.configuration_text = ''
        self.error_detail = ''
        self.guidance = ''
        self.dialog = ShortcutStatusDialog(menu)
        self.status_action.setEnabled(True)
        self.status_action.triggered.connect(self.show_status)
        self.configure_action.setEnabled(False)
        manager.assignment_changed.connect(self.assignment)
        manager.registration_failed.connect(self.failed)
        manager.identity_changed.connect(self.identity)
        manager.configuration_available_changed.connect(self.configuration_available)
        manager.configuration_message.connect(self.configuration_message)
        configure_action.triggered.connect(self.configure)
        self._render()

    def _short(self, text):
        # QAction rows cannot wrap; cap even arbitrary/localized backend prose.
        width = min(320, max(80, self.menu.screen().availableGeometry().width() - 80))
        return self.menu.fontMetrics().elidedText(text, Qt.ElideRight, width)

    def _render(self):
        self.assignment_text = (f'Requested shortcut: {display_shortcut(self.requested)}\n'
                                f'Assigned shortcut: {display_shortcut(self.actual)}\n'
                                f'Registration: {self.registration}')
        summary = self.assignment_text + f'\nApplication identity: {self.identity_text}'
        self.dialog.summary.setText(summary)
        details = '\n\n'.join(filter(None, [self.guidance, self.error_detail,
            self.identity_detail, self.configuration_text,
            f'Portal requested: {self.requested}\nPortal assigned: {self.actual}']))
        self.dialog.details.setPlainText(details)
        self.status_action.setText(self._short(f'Shortcut status: {self.registration}…'))
        self.identity_action.setText(self._short(f'Application identity: {self.identity_text}'))
        self.menu.status_label.setText(summary)
        self.tray.setToolTip('AI Snipping Tool\n' + '\n'.join(self._short(line) for line in summary.splitlines()))

    @Slot()
    def show_status(self):
        self.dialog.fit_to_screen()
        self.dialog.show()
        # This action is explicit; background portal updates never show/raise it.
        self.dialog.raise_()
        self.dialog.activateWindow()

    @Slot(str, str, str)
    def assignment(self, requested, actual, state):
        self.requested, self.actual = requested, actual
        self.error_detail = ''
        self.capture_action.setText('Capture' if state == 'unbound' else
            self._short(f'Capture ({display_shortcut(actual)})'))
        self.registration = {'match': 'Registered', 'different': 'Registered — different shortcut',
            'unknown': 'Registered — check assigned key', 'unbound': 'Not assigned'}.get(state, 'Unknown')
        self.guidance = ''
        if state in ('different', 'unbound'):
            self.guidance = ('Desktop chose a different shortcut. On GNOME open Settings → Apps → '
                'AI Snipping Tool → Permissions → Global Shortcuts → Open AI Snipping Tool '
                'capture menu → Set Shortcut. Press Alt+Shift+S and confirm. '
                'Cancel if it conflicts with another shortcut. Use tray Capture meanwhile.')
        self._render()

    @Slot(str)
    def failed(self, error):
        self.capture_action.setText('Capture')
        self.actual = 'Unavailable'
        self.registration = 'Registration failed — use tray Capture'
        self.error_detail = error
        self.configure_action.setEnabled(False)
        self._render()

    @Slot(str)
    def identity(self, status):
        self.identity_detail = status
        self.identity_text = ('Registered' if status.startswith('Host identity registered:')
                              else 'Not registered' if 'not registered' in status.lower() else 'Checking')
        self._render()

    @Slot(bool)
    def configuration_available(self, available):
        self.configure_action.setEnabled(available)
        self.configure_action.setText('Configure Shortcut…' if available else 'Configure Shortcut (unavailable)')
        self.configure_action.setToolTip('Open desktop shortcut configuration; changes require your confirmation.'
            if available else 'Unavailable on this portal. See Shortcut status → Show details for instructions.')

    @Slot()
    def configure(self):
        self.manager.request_configuration()

    @Slot(str)
    def configuration_message(self, message):
        self.configuration_text = message
        self._render()
