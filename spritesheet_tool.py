import sys
import os
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QFileDialog, QPushButton,
                             QSpinBox, QFrame, QStatusBar, QSizePolicy)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QTimer
from PIL import Image


class ImageSplitterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.fps = 12
        self.rows = 1
        self.cols = 1
        self.input_dir = ""
        self.output_dir = ""
        self.image_files = []
        self.current_idx = 0
        self.frames = []
        self.preview_frame_idx = 0

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation_preview)
        self.timer.start(1000 // self.fps)

    def init_ui(self):
        self.setWindowTitle("图片分割工具")
        self.resize(1100, 700)

        # 移除了 Segoe UI，使用系统默认 sans-serif 字体
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QWidget { color: #d4d4d4; font-family: sans-serif; }
            QLabel#PreviewLabel { background-color: #000000; border: 1px solid #333; }
            QFrame#ControlPanel { background-color: #252526; border-left: 1px solid #3c3c3c; }
            QPushButton { border: none; padding: 10px; border-radius: 4px; font-weight: bold; }
            QPushButton#BtnInput { background-color: #3a3d41; color: #ccc; }
            QPushButton#BtnInput[active="true"] { background-color: #0e639c; color: white; }
            QPushButton#BtnOutput { background-color: #d18e2a; color: black; }
            QPushButton#BtnOutput[active="true"] { background-color: #2d8a49; color: white; }
            QPushButton#BtnSave { background-color: #444; color: #888; }
            QPushButton#BtnSave[ready="true"] { background-color: #007acc; color: white; }
            QSpinBox { background-color: #3c3c3c; color: white; border: 1px solid #555; padding: 2px; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.source_view = QLabel("1. 点击右侧选择输入文件夹\n2. 点击右侧设置输出目录\n3. 方向键调整，Enter保存")
        self.source_view.setObjectName("PreviewLabel")
        self.source_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        main_layout.addWidget(self.source_view, stretch=3)

        control_panel = QFrame()
        control_panel.setObjectName("ControlPanel")
        control_panel.setFixedWidth(280)
        right_layout = QVBoxLayout(control_panel)

        right_layout.addWidget(QLabel("动画预览"))
        self.anim_view = QLabel()
        self.anim_view.setObjectName("PreviewLabel")
        self.anim_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anim_view.setFixedSize(250, 250)
        right_layout.addWidget(self.anim_view)

        self.info_label = QLabel("尚未加载数据")
        self.info_label.setStyleSheet("color: #9cdcfe; font-size: 12px; margin-top:10px;")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)

        right_layout.addSpacing(10)
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("帧率 (FPS):"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 120)
        self.spin_fps.setValue(12)
        self.spin_fps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.spin_fps.valueChanged.connect(self.on_fps_changed)
        fps_layout.addWidget(self.spin_fps)
        right_layout.addLayout(fps_layout)

        right_layout.addSpacing(20)

        self.btn_input = QPushButton("1. 选择输入文件夹")
        self.btn_input.setObjectName("BtnInput")
        self.btn_input.setProperty("active", "false")
        self.btn_input.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_input.clicked.connect(self.select_input_dir)
        right_layout.addWidget(self.btn_input)

        self.btn_output = QPushButton("2. 设置输出目录")
        self.btn_output.setObjectName("BtnOutput")
        self.btn_output.setProperty("active", "false")
        self.btn_output.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_output.clicked.connect(self.select_output_dir)
        right_layout.addWidget(self.btn_output)

        right_layout.addStretch()

        self.btn_save = QPushButton("确认保存 (Enter)")
        self.btn_save.setObjectName("BtnSave")
        self.btn_save.setProperty("ready", "false")
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save.setMinimumHeight(50)
        self.btn_save.clicked.connect(self.save_animation)
        right_layout.addWidget(self.btn_save)

        main_layout.addWidget(control_panel)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def predict_layout(self, pil_img):
        img_array = np.array(pil_img)
        if img_array.shape[2] < 4: return 1, 1
        alpha = img_array[:, :, 3]

        def count_segments(projection):
            binary = (projection > 0).astype(int)
            if not np.any(binary): return 1
            changes = np.diff(binary, prepend=0, append=0)
            return len(np.where(changes == 1)[0])

        row_p = np.max(alpha, axis=1)
        col_p = np.max(alpha, axis=0)
        return max(1, min(50, count_segments(row_p))), max(1, min(50, count_segments(col_p)))

    def select_input_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择素材文件夹")
        if path:
            # 只读取png文件
            files = sorted([f for f in os.listdir(path) if f.lower().endswith('.png')])
            if not files:
                self.status_bar.showMessage("该目录下没有PNG文件", 3000)
                return

            self.input_dir = path
            self.image_files = files
            self.current_idx = 0
            self.btn_input.setText(f"输入: {os.path.basename(path)}")
            self.btn_input.setProperty("active", "true")
            self.refresh_styles()
            self.load_image()

    def select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if path:
            self.output_dir = path
            self.btn_output.setText(f"输出: {os.path.basename(path)}")
            self.btn_output.setProperty("active", "true")
            self.refresh_styles()

    def refresh_styles(self):
        is_ready = bool(self.input_dir and self.output_dir and self.image_files)
        self.btn_save.setProperty("ready", "true" if is_ready else "false")
        for b in [self.btn_input, self.btn_output, self.btn_save]:
            b.style().unpolish(b)
            b.style().polish(b)

    def load_image(self):
        # 边界检查
        if 0 <= self.current_idx < len(self.image_files):
            file_path = os.path.join(self.input_dir, self.image_files[self.current_idx])
            try:
                self.pil_img = Image.open(file_path).convert("RGBA")
                self.rows, self.cols = self.predict_layout(self.pil_img)
                self.update_logic()
            except Exception as e:
                self.status_bar.showMessage(f"读取图片失败: {e}", 3000)
        else:
            self.pil_img = None
            self.frames = []
            self.source_view.setText("处理完毕！")
            self.anim_view.clear()
            self.info_label.setText("所有图片已处理完成")

    def update_logic(self):
        # 【修复核心】增加所有关键变量的有效性检查
        if not hasattr(self, 'pil_img') or self.pil_img is None:
            return
        if not self.image_files or self.current_idx >= len(self.image_files):
            return

        w, h = self.pil_img.size
        q_img = QImage(self.pil_img.tobytes(), w, h, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(q_img)
        painter = QPainter(pixmap)
        pen = QPen(QColor(255, 0, 0, 150))
        pen.setWidth(max(1, w // 600))
        painter.setPen(pen)

        cw, ch = w / self.cols, h / self.rows
        for i in range(1, self.cols):
            painter.drawLine(int(i * cw), 0, int(i * cw), h)
        for j in range(1, self.rows):
            painter.drawLine(0, int(j * ch), w, int(j * ch))
        painter.end()

        self.source_view.setPixmap(pixmap.scaled(self.source_view.size(),
                                                 Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))

        self.frames = []
        icw, ich = int(w // self.cols), int(h // self.rows)
        if icw > 0 and ich > 0:
            for r in range(self.rows):
                for c in range(self.cols):
                    box = (c * icw, r * ich, (c + 1) * icw, (r + 1) * ich)
                    frame = self.pil_img.crop(box)
                    if frame.getbbox(): self.frames.append(frame)

        self.info_label.setText(f"<b>当前文件:</b> {self.image_files[self.current_idx]}<br>"
                                f"<b>当前网格:</b> {self.rows}x{self.cols}<br>"
                                f"<b>有效帧数:</b> {len(self.frames)}<br>"
                                f"<b>进度:</b> {self.current_idx + 1}/{len(self.image_files)}")

    def update_animation_preview(self):
        if not self.frames:
            return
        self.preview_frame_idx = (self.preview_frame_idx + 1) % len(self.frames)
        f = self.frames[self.preview_frame_idx]
        q_img = QImage(f.tobytes(), f.size[0], f.size[1], QImage.Format.Format_RGBA8888)
        self.anim_view.setPixmap(QPixmap.fromImage(q_img).scaled(
            self.anim_view.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def on_fps_changed(self):
        self.fps = self.spin_fps.value()
        self.timer.setInterval(1000 // self.fps)

    def save_animation(self):
        if self.btn_save.property("ready") != "true" or not self.frames:
            return

        try:
            name = os.path.splitext(self.image_files[self.current_idx])[0]
            save_path = os.path.join(self.output_dir, f"{name}.webp")
            self.frames[0].save(save_path, save_all=True, append_images=self.frames[1:],
                                duration=1000 // self.fps, loop=0, lossless=True)
            self.status_bar.showMessage(f"已保存: {name}.webp", 2000)
            self.current_idx += 1
            self.load_image()
        except Exception as e:
            self.status_bar.showMessage(f"保存失败: {e}", 3000)

    def keyPressEvent(self, event):
        # 如果没有图片，按键不执行逻辑，防止报错
        if not self.image_files or self.current_idx >= len(self.image_files):
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Up:
            self.rows = min(100, self.rows + 1)
        elif event.key() == Qt.Key.Key_Down:
            self.rows = max(1, self.rows - 1)
        elif event.key() == Qt.Key.Key_Right:
            self.cols = min(100, self.cols + 1)
        elif event.key() == Qt.Key.Key_Left:
            self.cols = max(1, self.cols - 1)
        elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self.save_animation()
            return
        elif event.key() == Qt.Key.Key_Escape:
            self.close()

        self.update_logic()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'pil_img') and self.pil_img:
            self.update_logic()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageSplitterApp()
    window.show()
    sys.exit(app.exec())