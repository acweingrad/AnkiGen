from aqt import mw
from aqt.qt import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget, Qt,
)
from aqt.utils import showInfo, showWarning

from ..core.config import get_provider_label, normalize_config
from ..core.services.card_generation import CardGenerationService
from .card_widget import CardWidget
from .config_dialog import ConfigDialog
from .paste_area import PasteArea
from .style import apply_terminal_style

try:
    from aqt.operations import QueryOp
    HAS_QUERY_OP = True
except ImportError:
    HAS_QUERY_OP = False

DOMAINS = ["(any)", "pharmacology", "anatomy", "pathophysiology", "clinical", "microbiology", "biochemistry"]
CARD_TYPES = ["Mixed", "Basic only", "Cloze only"]
_CARD_TYPE_VALUES = {"Mixed": "mixed", "Basic only": "basic", "Cloze only": "cloze"}
CLOZE_MODES = ["Single", "Multi"]
_CLOZE_MODE_VALUES = {"Single": "single", "Multi": "multi"}
_STATUS_STYLE = "color: #666666; font-family: SF Mono, Menlo, Monaco, Courier New, monospace;"


class MedicalCardDialog(QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = normalize_config(config)
        self._card_widgets: list[CardWidget] = []
        self.setWindowTitle("Medical Flashcard Generator")
        self.setMinimumSize(680, 700)
        apply_terminal_style(self)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self._screens = QStackedWidget()
        root.addWidget(self._screens)

        self._build_input_page()
        self._build_review_page()
        self._screens.setCurrentWidget(self._input_page)

    def _build_input_page(self):
        self._input_page = QWidget()
        root = QVBoxLayout(self._input_page)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        topic_tab = QWidget()
        topic_layout = QVBoxLayout(topic_tab)
        domain_row = QHBoxLayout()
        domain_row.addWidget(QLabel("Domain:"))
        self._domain_combo = QComboBox()
        self._domain_combo.addItems(DOMAINS)
        domain_row.addWidget(self._domain_combo)
        domain_row.addStretch()
        topic_layout.addLayout(domain_row)
        topic_layout.addWidget(QLabel("Topic or question:"))
        self._topic_edit = QLineEdit()
        self._topic_edit.setPlaceholderText('e.g. "ACE inhibitors" or "brachial plexus"')
        self._topic_edit.returnPressed.connect(self._on_generate_clicked)
        topic_layout.addWidget(self._topic_edit)
        topic_layout.addStretch()
        self._tabs.addTab(topic_tab, "Topic")

        paste_tab = QWidget()
        paste_layout = QVBoxLayout(paste_tab)
        self._paste_area = PasteArea()
        paste_layout.addWidget(self._paste_area)
        self._tabs.addTab(paste_tab, "Paste Text")

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Deck:"))
        self._deck_edit = QLineEdit(self.config.get("default_deck", "Medical::AI Generated"))
        self._deck_edit.setMinimumWidth(200)
        ctrl_row.addWidget(self._deck_edit)
        ctrl_row.addWidget(QLabel("Type:"))
        self._card_type_combo = QComboBox()
        self._card_type_combo.addItems(CARD_TYPES)
        self._card_type_combo.currentTextChanged.connect(self._sync_cloze_mode_enabled)
        ctrl_row.addWidget(self._card_type_combo)
        ctrl_row.addWidget(QLabel("Cloze:"))
        self._cloze_mode_combo = QComboBox()
        self._cloze_mode_combo.addItems(CLOZE_MODES)
        self._cloze_mode_combo.setCurrentText("Multi")
        ctrl_row.addWidget(self._cloze_mode_combo)
        ctrl_row.addWidget(QLabel("Cards:"))
        self._n_cards_spin = QSpinBox()
        self._n_cards_spin.setRange(1, 100)
        self._n_cards_spin.setValue(self.config.get("cards_per_topic", 10))
        ctrl_row.addWidget(self._n_cards_spin)
        ctrl_row.addStretch()
        self._generate_btn = QPushButton("[ Generate ]")
        self._generate_btn.setDefault(True)
        self._generate_btn.clicked.connect(self._on_generate_clicked)
        ctrl_row.addWidget(self._generate_btn)
        self._review_btn = QPushButton("[ Review Cards ]")
        self._review_btn.setEnabled(False)
        self._review_btn.clicked.connect(self._show_review_page)
        ctrl_row.addWidget(self._review_btn)
        settings_btn = QPushButton("[ Settings ]")
        settings_btn.clicked.connect(self._open_settings)
        ctrl_row.addWidget(settings_btn)
        root.addLayout(ctrl_row)

        self._input_status_label = QLabel("")
        self._input_status_label.setStyleSheet(_STATUS_STYLE)
        root.addWidget(self._input_status_label)

        self._sync_cloze_mode_enabled()
        self._screens.addWidget(self._input_page)

    def _build_review_page(self):
        self._review_page = QWidget()
        root = QVBoxLayout(self._review_page)

        top_row = QHBoxLayout()
        self._edit_inputs_btn = QPushButton("[ Edit Inputs ]")
        self._edit_inputs_btn.clicked.connect(self._show_input_page)
        top_row.addWidget(self._edit_inputs_btn)

        self._review_status_label = QLabel("")
        self._review_status_label.setStyleSheet(_STATUS_STYLE)
        top_row.addWidget(self._review_status_label, stretch=1)

        reject_all_btn = QPushButton("[ Reject All ]")
        reject_all_btn.clicked.connect(self._reject_all)
        top_row.addWidget(reject_all_btn)

        self._add_btn = QPushButton("[ Add All to Anki ]")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._add_all_to_anki)
        top_row.addWidget(self._add_btn)
        root.addLayout(top_row)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll_area.setWidget(self._card_container)
        root.addWidget(self._scroll_area, stretch=1)

        self._screens.addWidget(self._review_page)

    # ── Generate ───────────────────────────────────────────────────

    def _collect_prompt_data(self) -> dict:
        tab = self._tabs.currentIndex()
        mode = "topic" if tab == 0 else "paste"
        domain_text = self._domain_combo.currentText()
        domain = None if domain_text == "(any)" else domain_text
        card_type = _CARD_TYPE_VALUES[self._card_type_combo.currentText()]
        cloze_mode = _CLOZE_MODE_VALUES[self._cloze_mode_combo.currentText()]
        # Pasted lecture/PDF material maps best to AnKing-style cloze notes.
        if mode == "paste" and card_type == "mixed":
            card_type = "cloze"
        return {
            "mode": mode,
            "topic": self._topic_edit.text().strip(),
            "text": self._paste_area.get_text(),
            "images": self._paste_area.get_images() if mode == "paste" else [],
            "card_type": card_type,
            "cloze_mode": cloze_mode,
            "domain": domain,
            "deck": self._deck_edit.text().strip() or "Medical::AI Generated",
            "n_cards": self._n_cards_spin.value(),
            "domain_hints": self.config.get("domain_hints", True),
        }

    def _on_generate_clicked(self):
        prompt_data = self._collect_prompt_data()

        if prompt_data["mode"] == "topic" and not prompt_data["topic"]:
            showWarning("Please enter a topic.", parent=self)
            return
        if prompt_data["mode"] == "paste" and not prompt_data["text"].strip() and not prompt_data["images"]:
            showWarning("Please paste some text or a screenshot.", parent=self)
            return

        self._show_input_page()
        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("[ Generating… ]")
        self._add_btn.setEnabled(False)
        self._review_btn.setEnabled(False)
        self._input_status_label.setText(f"Generating cards via {self._provider_label()}…")
        self._review_status_label.setText("")
        self._clear_card_list()

        if HAS_QUERY_OP:
            op = QueryOp(
                parent=self,
                op=lambda col: self._run_api_call(prompt_data),
                success=self._on_cards_received,
            ).failure(self._on_api_error)
            op.run_in_background()
        else:
            # Fallback for older Anki: blocking call on main thread
            try:
                cards = self._run_api_call(prompt_data)
                self._on_cards_received(cards)
            except Exception as exc:
                self._on_api_error(exc)

    def _run_api_call(self, prompt_data: dict) -> list:
        """Runs on a background thread — no Qt calls."""
        service = CardGenerationService(self.config)
        return service.generate_cards(prompt_data)

    def _on_cards_received(self, result):
        cards, warnings = result
        self._generate_btn.setEnabled(True)
        self._generate_btn.setText("[ Generate ]")
        self._populate_card_list(cards)
        if warnings:
            status = f"{len(cards)} cards ready. Warnings: {'; '.join(warnings)}"
        else:
            status = f"{len(cards)} cards ready for review."
        self._input_status_label.setText(status)
        self._review_status_label.setText(status)
        if cards:
            self._show_review_page()

    def _on_api_error(self, exc: Exception):
        self._generate_btn.setEnabled(True)
        self._generate_btn.setText("[ Generate ]")
        self._show_input_page()
        self._input_status_label.setText("")
        self._review_status_label.setText("")
        showWarning(f"Error generating cards:\n\n{exc}", parent=self)

    # ── Card list ──────────────────────────────────────────────────

    def _clear_card_list(self):
        for w in self._card_widgets:
            w.setParent(None)
        self._card_widgets.clear()
        self._add_btn.setEnabled(False)
        self._review_btn.setEnabled(False)

    def _populate_card_list(self, cards: list):
        self._clear_card_list()
        for card_data in cards:
            widget = CardWidget(card_data, parent=self._card_container)
            self._card_layout.addWidget(widget)
            self._card_widgets.append(widget)
        self._add_btn.setEnabled(bool(cards))
        self._review_btn.setEnabled(bool(cards))

    def _reject_all(self):
        for w in self._card_widgets:
            if not w.is_rejected():
                w._toggle_reject()

    # ── Add to Anki ────────────────────────────────────────────────

    def _add_all_to_anki(self):
        from ..core.anki_bridge import add_cards_to_collection
        to_add = [w.get_card_data() for w in self._card_widgets if not w.is_rejected()]
        if not to_add:
            showWarning("All cards have been rejected. Nothing to add.", parent=self)
            return
        n_added, errors = add_cards_to_collection(to_add)
        msg = f"{n_added} card(s) added to Anki."
        if errors:
            msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors)
        showInfo(msg, parent=self)
        if n_added > 0:
            self._clear_card_list()
            self._paste_area.clear_all()
            self._review_status_label.setText("")
            self._show_input_page()
            self._input_status_label.setText(f"{n_added} card(s) added.")

    # ── Settings ───────────────────────────────────────────────────

    def _open_settings(self):
        dlg = ConfigDialog(self, self.config)
        if dlg.exec():
            self.config = normalize_config(mw.addonManager.getConfig("medical_card_generator"))

    def _provider_label(self) -> str:
        return get_provider_label(self.config.get("provider", "anthropic"))

    def _sync_cloze_mode_enabled(self):
        is_basic_only = self._card_type_combo.currentText() == "Basic only"
        self._cloze_mode_combo.setEnabled(not is_basic_only)

    def _show_input_page(self):
        self._screens.setCurrentWidget(self._input_page)

    def _show_review_page(self):
        self._screens.setCurrentWidget(self._review_page)
