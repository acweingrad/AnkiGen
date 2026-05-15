from aqt.qt import (
    QFrame, QHBoxLayout, QImage, QLabel, QLineEdit, QPlainTextEdit,
    QPixmap, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, Qt,
)


class CardWidget(QFrame):
    """
    Displays one generated card with front/back/tags (basic) or text/back_extra/tags (cloze).
    Supports inline editing and reject/undo-reject toggling.
    """

    def __init__(self, card_data: dict, parent=None):
        super().__init__(parent)
        self._card_type = card_data.get("card_type", "basic")
        if self._card_type == "cloze":
            self._data = {
                "card_type": "cloze",
                "text": card_data.get("text", ""),
                "back_extra": card_data.get("back_extra", ""),
                "tags": list(card_data.get("tags", [])),
                "deck": card_data.get("deck", "Medical::AI Generated"),
                "images": list(card_data.get("images", [])),
            }
        else:  # basic or basic_reversed
            self._data = {
                "card_type": self._card_type,
                "front": card_data.get("front", ""),
                "back": card_data.get("back", ""),
                "tags": list(card_data.get("tags", [])),
                "deck": card_data.get("deck", "Medical::AI Generated"),
                "images": list(card_data.get("images", [])),
            }
        self._rejected = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        # ── View mode ──────────────────────────────────────────────
        view_widget = QFrame()
        view_layout = QVBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)

        # Type badge
        _badge_text = {"cloze": "CLOZE", "basic_reversed": "BASIC (REVERSED)"}.get(
            self._card_type, "BASIC"
        )
        type_badge = QLabel(_badge_text)
        type_badge.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #888888; letter-spacing: 1px;"
        )
        view_layout.addWidget(type_badge)

        self._primary_label = QLabel()
        self._primary_label.setWordWrap(True)
        self._primary_label.setStyleSheet("font-weight: bold; color: #d97757;")
        view_layout.addWidget(self._primary_label)

        self._secondary_label = QLabel()
        self._secondary_label.setWordWrap(True)
        view_layout.addWidget(self._secondary_label)

        self._image_row = QHBoxLayout()
        self._image_row.setSpacing(4)
        self._image_row.setContentsMargins(0, 4, 0, 0)
        view_layout.addLayout(self._image_row)

        self._tags_label = QLabel()
        self._tags_label.setStyleSheet("color: #555555; font-size: 11px;")
        view_layout.addWidget(self._tags_label)

        self._refresh_view_labels()

        btn_row = QHBoxLayout()
        self._edit_btn = QPushButton("[ Edit ]")
        self._edit_btn.setFixedWidth(80)
        self._edit_btn.clicked.connect(self._enter_edit_mode)
        self._reject_btn = QPushButton("[ Reject ]")
        self._reject_btn.setFixedWidth(80)
        self._reject_btn.clicked.connect(self._toggle_reject)
        btn_row.addStretch()
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._reject_btn)
        view_layout.addLayout(btn_row)

        self._stack.addWidget(view_widget)

        # ── Edit mode ──────────────────────────────────────────────
        edit_widget = QFrame()
        edit_layout = QVBoxLayout(edit_widget)
        edit_layout.setContentsMargins(0, 0, 0, 0)

        if self._card_type == "cloze":
            edit_layout.addWidget(QLabel("Text (with {{c1::...}} deletions):"))
            self._primary_edit = QPlainTextEdit(self._data["text"])
            self._primary_edit.setFixedHeight(80)
            edit_layout.addWidget(self._primary_edit)

            edit_layout.addWidget(QLabel("Back Extra (optional):"))
            self._secondary_edit = QPlainTextEdit(self._data["back_extra"])
            self._secondary_edit.setFixedHeight(50)
            edit_layout.addWidget(self._secondary_edit)
        else:
            edit_layout.addWidget(QLabel("Front:"))
            self._primary_edit = QPlainTextEdit(self._data["front"])
            self._primary_edit.setFixedHeight(60)
            edit_layout.addWidget(self._primary_edit)

            edit_layout.addWidget(QLabel("Back:"))
            self._secondary_edit = QPlainTextEdit(self._data["back"])
            self._secondary_edit.setFixedHeight(80)
            edit_layout.addWidget(self._secondary_edit)

        edit_layout.addWidget(QLabel("Tags (space-separated):"))
        self._tags_edit = QLineEdit(" ".join(self._data["tags"]))
        edit_layout.addWidget(self._tags_edit)

        edit_layout.addWidget(QLabel("Deck:"))
        self._deck_edit = QLineEdit(self._data["deck"])
        edit_layout.addWidget(self._deck_edit)

        save_row = QHBoxLayout()
        save_btn = QPushButton("[ Save ]")
        save_btn.clicked.connect(self._save_edit)
        cancel_btn = QPushButton("[ Cancel ]")
        cancel_btn.clicked.connect(self._cancel_edit)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        save_row.addWidget(cancel_btn)
        edit_layout.addLayout(save_row)

        self._stack.addWidget(edit_widget)
        self._stack.setCurrentIndex(0)

    def _refresh_view_labels(self):
        if self._card_type == "cloze":
            self._primary_label.setText(f"Cloze: {self._data['text']}")
            extra = self._data.get("back_extra", "")
            self._secondary_label.setText(f"Extra: {extra}" if extra else "")
            self._secondary_label.setVisible(bool(extra))
        else:
            self._primary_label.setText(f"Q: {self._data['front']}")
            self._secondary_label.setText(f"A: {self._data['back']}")
            self._secondary_label.setVisible(True)
        tags_str = "  |  ".join(self._data["tags"]) if self._data["tags"] else "(no tags)"
        self._tags_label.setText(f"Tags: {tags_str}   Deck: {self._data['deck']}")
        self._refresh_image_thumbnails()

    def _refresh_image_thumbnails(self):
        while self._image_row.count():
            item = self._image_row.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        for png_bytes in self._data["images"]:
            img = QImage.fromData(png_bytes)
            if not img.isNull():
                pixmap = QPixmap.fromImage(img).scaledToHeight(
                    60, Qt.TransformationMode.SmoothTransformation
                )
                lbl = QLabel()
                lbl.setPixmap(pixmap)
                lbl.setStyleSheet("border: 1px solid #2a2a2a;")
                self._image_row.addWidget(lbl)
        if self._data["images"]:
            self._image_row.addStretch()

    def _enter_edit_mode(self):
        if self._card_type == "cloze":
            self._primary_edit.setPlainText(self._data["text"])
            self._secondary_edit.setPlainText(self._data.get("back_extra", ""))
        else:
            self._primary_edit.setPlainText(self._data["front"])
            self._secondary_edit.setPlainText(self._data["back"])
        self._tags_edit.setText(" ".join(self._data["tags"]))
        self._deck_edit.setText(self._data["deck"])
        self._stack.setCurrentIndex(1)

    def _save_edit(self):
        if self._card_type == "cloze":
            self._data["text"] = self._primary_edit.toPlainText().strip()
            self._data["back_extra"] = self._secondary_edit.toPlainText().strip()
        else:
            self._data["front"] = self._primary_edit.toPlainText().strip()
            self._data["back"] = self._secondary_edit.toPlainText().strip()
        raw_tags = self._tags_edit.text().strip()
        self._data["tags"] = [t for t in raw_tags.split() if t]
        self._data["deck"] = self._deck_edit.text().strip() or "Medical::AI Generated"
        self._refresh_view_labels()
        self._stack.setCurrentIndex(0)

    def _cancel_edit(self):
        self._stack.setCurrentIndex(0)

    def _toggle_reject(self):
        self._rejected = not self._rejected
        if self._rejected:
            self.setStyleSheet(
                "QFrame { background-color: #0d0d0d; border-left: 2px solid #5a1a1a; }"
                "QLabel { color: #444444; text-decoration: line-through; }"
            )
            self._reject_btn.setText("[ Undo ]")
            self._edit_btn.setEnabled(False)
        else:
            self.setStyleSheet("")
            self._primary_label.setStyleSheet("font-weight: bold; color: #d97757;")
            self._tags_label.setStyleSheet("color: #555555; font-size: 11px;")
            self._reject_btn.setText("[ Reject ]")
            self._edit_btn.setEnabled(True)

    def is_rejected(self) -> bool:
        return self._rejected

    def get_card_data(self) -> dict:
        return dict(self._data)
