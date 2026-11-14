"""Main-thread presentation for portal shortcut and identity diagnostics."""
from PySide6.QtCore import QObject, Slot


class ShortcutStatus(QObject):
    def __init__(self, menu, manager, tray, capture_action, status_action,
                 identity_action, configure_action):
        super().__init__(menu)
        self.menu, self.manager, self.tray = menu, manager, tray
        self.capture_action, self.status_action = capture_action, status_action
        self.identity_action, self.configure_action = identity_action, configure_action
        self.assignment_text = 'Shortcut: waiting for desktop assignment'
        self.identity_text = 'Application identity: checking'
        self.configuration_text = ''
        self.configure_action.setEnabled(False)
        manager.assignment_changed.connect(self.assignment)
        manager.registration_failed.connect(self.failed)
        manager.identity_changed.connect(self.identity)
        manager.configuration_available_changed.connect(self.configuration_available)
        manager.configuration_message.connect(self.configuration_message)
        configure_action.triggered.connect(self.configure)
        self._render()

    def _render(self):
        self.status_action.setText(self.assignment_text)
        self.identity_action.setText(self.identity_text)
        details = '\n'.join(filter(None, [self.assignment_text, self.identity_text,
                                           self.configuration_text]))
        self.menu.status_label.setText(details)
        self.tray.setToolTip('AI Snipping Tool\n' + details)

    @Slot(str, str, str)
    def assignment(self, requested, actual, state):
        self.capture_action.setText('Capture' if state == 'unbound' else f'Capture ({actual})')
        self.assignment_text = f'Requested: {requested}; assigned: {actual}'
        if state == 'different':
            self.assignment_text += ' — Desktop chose a different shortcut. Use Configure Shortcut when available to change it.'
        elif state == 'unknown':
            self.assignment_text += ' — Compare the desktop assignment with your request.'
        elif state == 'unbound':
            self.assignment_text += ' — Use tray Capture or configure a shortcut.'
        self._render()

    @Slot(str)
    def failed(self, error):
        self.capture_action.setText('Capture')
        self.assignment_text = f'Shortcut unavailable: {error}. Use tray Capture.'
        self.configure_action.setEnabled(False)
        self._render()

    @Slot(str)
    def identity(self, status):
        self.identity_text = status
        self._render()

    @Slot(bool)
    def configuration_available(self, available):
        self.configure_action.setEnabled(available)
        self.configure_action.setText('Configure Shortcut…' if available else 'Configure Shortcut (unavailable)')
        self.configure_action.setToolTip('Open desktop shortcut configuration; changes require your confirmation.'
            if available else 'Unavailable: desktop backend support (GlobalShortcuts v2) and a registered host identity are required. See status for details.')

    @Slot()
    def configure(self):
        self.manager.request_configuration()

    @Slot(str)
    def configuration_message(self, message):
        self.configuration_text = message
        self._render()
