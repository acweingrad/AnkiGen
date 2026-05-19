try:
    from aqt import gui_hooks, mw
    from aqt.qt import QAction
except ImportError:
    gui_hooks = None
    mw = None
    QAction = None

from .core.config import has_provider_credentials, normalize_config


def _open_generator():
    config = normalize_config(mw.addonManager.getConfig(__name__) or {})

    if not has_provider_credentials(config):
        from .ui.config_dialog import ConfigDialog
        dlg = ConfigDialog(mw, config)
        if not dlg.exec():
            return
        config = normalize_config(mw.addonManager.getConfig(__name__) or {})

    from .ui.main_dialog import MedicalCardDialog
    dlg = MedicalCardDialog(mw, config)
    dlg.exec()


def _setup_menu():
    action = QAction("Generate Medical Cards", mw)
    action.triggered.connect(_open_generator)
    mw.form.menuTools.addAction(action)


if gui_hooks is not None:
    gui_hooks.main_window_did_init.append(_setup_menu)
