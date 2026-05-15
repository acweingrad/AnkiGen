from aqt.qt import (
    QBuffer, QByteArray, QFileDialog, QHBoxLayout, QIODevice, QImage, QLabel,
    QPushButton, QPixmap, QPlainTextEdit, QScrollArea,
    QVBoxLayout, QWidget, Qt, pyqtSignal,
)
from typing import Optional

try:
    from PyQt6.QtPdf import QPdfDocument
    _HAS_QTPDF = True
except ImportError:
    _HAS_QTPDF = False

MAX_LONG_EDGE = 1568
PDF_RENDER_LONG_EDGE = 1024
PDF_PAGE_LIMIT = 20


def _pdf_no_error_value():
    """PyQt bindings have used both `None_` and `none_` for the success value."""
    return getattr(
        QPdfDocument.Error,
        "None_",
        getattr(QPdfDocument.Error, "none_", getattr(QPdfDocument.Error, "None", None)),
    )


class _ImagePasteEdit(QPlainTextEdit):
    image_pasted = pyqtSignal(QImage)

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self.image_pasted.emit(img)
            return
        super().insertFromMimeData(source)


class PasteArea(QWidget):
    """Text input that accepts pasted images and PDF uploads, shown as removable thumbnails."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: list[Optional[bytes]] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if _HAS_QTPDF:
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.addStretch()
            self._pdf_btn = QPushButton("[ Upload PDF ]")
            self._pdf_btn.setFixedWidth(120)
            self._pdf_btn.clicked.connect(self._on_upload_pdf)
            btn_row.addWidget(self._pdf_btn)
            layout.addLayout(btn_row)

        self._edit = _ImagePasteEdit()
        self._edit.setPlaceholderText(
            "Paste lecture notes or textbook text…\n"
            "You can also paste slide screenshots (Ctrl+V) — "
            "they will appear on the back of relevant cards."
            + ("\nOr upload a PDF above to generate from lecture slides." if _HAS_QTPDF else "")
        )
        self._edit.image_pasted.connect(self._on_image_pasted)
        layout.addWidget(self._edit)

        self._pdf_status = QLabel("")
        self._pdf_status.setStyleSheet("color: #888888; font-size: 11px;")
        self._pdf_status.setVisible(False)
        layout.addWidget(self._pdf_status)

        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setFixedHeight(104)
        self._thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setVisible(False)
        self._thumb_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #2a2a2a; background: #0a0a0a; }"
        )

        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._thumb_layout.setContentsMargins(4, 4, 4, 4)
        self._thumb_layout.setSpacing(6)
        self._thumb_scroll.setWidget(self._thumb_container)
        layout.addWidget(self._thumb_scroll)

    # ── PDF upload ─────────────────────────────────────────────────

    def _on_upload_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF files (*.pdf)"
        )
        if path:
            self._load_pdf(path)

    def _load_pdf(self, path: str):
        from PyQt6.QtCore import QSize, QSizeF

        doc = QPdfDocument(None)
        load_error = doc.load(path)
        if load_error != _pdf_no_error_value():
            self._pdf_status.setText(f"Failed to load PDF ({load_error})")
            self._pdf_status.setVisible(True)
            return

        if doc.status() != QPdfDocument.Status.Ready:
            self._pdf_status.setText(f"Failed to prepare PDF (status {doc.status()})")
            self._pdf_status.setVisible(True)
            return

        total = doc.pageCount()
        to_render = min(total, PDF_PAGE_LIMIT)

        for i in range(to_render):
            page_size: QSizeF = doc.pagePointSize(i)
            w, h = page_size.width(), page_size.height()
            long_edge = max(w, h, 1)
            scale = PDF_RENDER_LONG_EDGE / long_edge
            render_size = QSize(max(1, int(w * scale)), max(1, int(h * scale)))
            qimage = doc.render(i, render_size)

            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            qimage.save(buf, "PNG")
            png_bytes = bytes(buf.data())
            buf.close()

            idx = len(self._images)
            self._images.append(png_bytes)
            self._add_thumbnail_cell(qimage, idx, label=f"p.{i + 1}")

        doc.close()
        self._thumb_scroll.setVisible(True)

        if total > PDF_PAGE_LIMIT:
            self._pdf_status.setText(
                f"PDF loaded: first {PDF_PAGE_LIMIT} of {total} pages used."
            )
        else:
            self._pdf_status.setText(f"PDF loaded: {total} page(s).")
        self._pdf_status.setVisible(True)

    # ── Screenshot paste ───────────────────────────────────────────

    def _on_image_pasted(self, img: QImage):
        if img.width() > MAX_LONG_EDGE or img.height() > MAX_LONG_EDGE:
            img = img.scaled(
                MAX_LONG_EDGE, MAX_LONG_EDGE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        png_bytes = bytes(buf.data())
        buf.close()

        idx = len(self._images)
        self._images.append(png_bytes)
        self._add_thumbnail_cell(img, idx)
        self._thumb_scroll.setVisible(True)

    # ── Thumbnails ─────────────────────────────────────────────────

    def _add_thumbnail_cell(self, img: QImage, idx: int, label: str = ""):
        cell = QWidget()
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(2, 2, 2, 2)
        cell_layout.setSpacing(2)

        if label:
            page_label = QLabel(label)
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_label.setStyleSheet("color: #888888; font-size: 10px;")
            cell_layout.addWidget(page_label)

        pixmap = QPixmap.fromImage(img).scaledToHeight(
            68 if not label else 54, Qt.TransformationMode.SmoothTransformation
        )
        thumb = QLabel()
        thumb.setPixmap(pixmap)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.addWidget(thumb)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(max(pixmap.width(), 20), 16)
        remove_btn.setStyleSheet(
            "QPushButton { font-size: 10px; padding: 0; color: #888; border: none; }"
            "QPushButton:hover { color: #d97757; }"
        )
        remove_btn.clicked.connect(lambda _, i=idx, c=cell: self._remove_entry(i, c))
        cell_layout.addWidget(remove_btn)

        self._thumb_layout.addWidget(cell)

    def _remove_entry(self, idx: int, cell: QWidget):
        if 0 <= idx < len(self._images):
            self._images[idx] = None
        cell.setParent(None)
        if all(b is None for b in self._images):
            self._thumb_scroll.setVisible(False)

    # ── Public API ─────────────────────────────────────────────────

    def get_text(self) -> str:
        return self._edit.toPlainText()

    def get_images(self) -> list[bytes]:
        return [b for b in self._images if b is not None]

    def clear_all(self):
        self._edit.clear()
        self._images.clear()
        while self._thumb_layout.count():
            item = self._thumb_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        self._thumb_scroll.setVisible(False)
        self._pdf_status.setVisible(False)
        self._pdf_status.setText("")
