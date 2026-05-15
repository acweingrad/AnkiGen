from aqt import mw
from aqt.qt import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QVBoxLayout, Qt,
)

from ..core.config import (
    DEFAULT_MODEL_BY_PROVIDER,
    get_provider_api_key,
    get_provider_api_key_placeholder,
    get_provider_choices,
    get_provider_label,
    normalize_config,
    set_provider_api_key,
)
from .style import apply_terminal_style


class ConfigDialog(QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = normalize_config(config)
        self.setWindowTitle("Medical Flashcard Generator — Settings")
        self.setMinimumWidth(460)
        apply_terminal_style(self)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        warning = QLabel(
            "⚠  API key stored in plaintext in Anki's add-on config folder. "
            "Do not share that folder."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d97757; font-family: SF Mono, Menlo, Monaco, Courier New, monospace;")
        layout.addWidget(warning)

        form = QFormLayout()
        layout.addLayout(form)

        self.provider_combo = QComboBox()
        for provider_key, label in get_provider_choices():
            self.provider_combo.addItem(label, provider_key)
        current_provider = self.config.get("provider", "anthropic")
        current_index = self.provider_combo.findData(current_provider)
        if current_index >= 0:
            self.provider_combo.setCurrentIndex(current_index)
        self.provider_combo.currentIndexChanged.connect(self._sync_provider_fields)
        form.addRow("Model Provider:", self.provider_combo)

        self.api_key_field = QLineEdit(get_provider_api_key(self.config, current_provider))
        self.api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_label = QLabel()
        form.addRow(self._api_key_label, self.api_key_field)

        self.model_field = QLineEdit(self.config.get("model", ""))
        form.addRow("Model:", self.model_field)

        self.deck_field = QLineEdit(self.config.get("default_deck", "Medical::AI Generated"))
        self.deck_field.setPlaceholderText("Medical::AI Generated")
        form.addRow("Default Deck:", self.deck_field)

        self.cards_spinner = QSpinBox()
        self.cards_spinner.setRange(1, 25)
        self.cards_spinner.setValue(self.config.get("cards_per_topic", 10))
        form.addRow("Cards per Topic (default):", self.cards_spinner)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._sync_provider_fields()

    def _current_provider(self) -> str:
        return self.provider_combo.currentData() or "anthropic"

    def _sync_provider_fields(self):
        provider = self._current_provider()
        self._api_key_label.setText(f"{get_provider_label(provider)} API Key:")
        self.api_key_field.setPlaceholderText(get_provider_api_key_placeholder(provider))
        if not self.model_field.text().strip():
            self.model_field.setText(DEFAULT_MODEL_BY_PROVIDER.get(provider, ""))

    def accept(self):
        provider = self._current_provider()
        self.config["provider"] = provider
        self.config = set_provider_api_key(self.config, provider, self.api_key_field.text().strip())
        self.config["model"] = self.model_field.text().strip() or DEFAULT_MODEL_BY_PROVIDER.get(provider, "")
        self.config["default_deck"] = self.deck_field.text().strip() or "Medical::AI Generated"
        self.config["cards_per_topic"] = self.cards_spinner.value()
        mw.addonManager.writeConfig("medical_card_generator", self.config)
        super().accept()
