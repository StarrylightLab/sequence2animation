import os
import numpy as np
from PIL import Image
import pygame
import sys

# ========== 可调参数 ==========
input_folder = "/Users/nayuchuanmei/Documents/[需要处理的]"  # 输入文件夹路径
output_folder = "output"  # 输出文件夹路径
fps = 12  # 动画帧率
format = "webp"  # 可选 "webp" 或 "apng"
alpha_threshold = 28  # alpha 阈值 (0-255)
max_rows = 20  # 最大行分割数
max_cols = 20  # 最大列分割数
debug = True  # 是否打印调试信息
preview_max_size = (1200, 800)  # 预览窗口最大尺寸
# ==============================

os.makedirs(output_folder, exist_ok=True)


def detect_max_rows(img, max_rows, alpha_threshold):
    """从最大行开始递减，找到每行上下边缘都透明的最大行数"""
    w, h = img.size
    arr = np.array(img)

    for rows in range(max_rows, 0, -1):
        frame_h = h // rows
        all_clear = True
        for i in range(rows):
            top = arr[i * frame_h, :, 3]
            bottom = arr[(i + 1) * frame_h - 1, :, 3]
            if np.any(top >= alpha_threshold) or np.any(bottom >= alpha_threshold):
                all_clear = False
                if debug:
                    print(f"行检测失败: rows={rows}, 切片{i}, top/bottom有不透明像素")
                break
        if all_clear:
            if debug:
                print(f"✅ 最大有效行数: {rows}")
            return rows
    if debug:
        print("⚠️ 找不到符合条件的行，默认1行")
    return 1


def detect_max_cols(img, max_cols, alpha_threshold, rows):
    """从最大列开始递减，找到每列左右边缘都透明的最大列数"""
    w, h = img.size
    arr = np.array(img)

    for cols in range(max_cols, 0, -1):
        frame_w = w // cols
        all_clear = True
        for j in range(cols):
            left = arr[:, j * frame_w, 3]
            right = arr[:, (j + 1) * frame_w - 1, 3]
            for i in range(rows):
                slice_top = i * (h // rows)
                slice_bottom = (i + 1) * (h // rows)
                if np.any(left[slice_top:slice_bottom] >= alpha_threshold) or np.any(
                        right[slice_top:slice_bottom] >= alpha_threshold):
                    all_clear = False
                    if debug:
                        print(f"列检测失败: cols={cols}, 切片({i},{j}), left/right有不透明像素")
                    break
            if not all_clear:
                break
        if all_clear:
            if debug:
                print(f"✅ 最大有效列数: {cols}")
            return cols
    if debug:
        print("⚠️ 找不到符合条件的列，默认1列")
    return 1


def auto_split_and_animate(filepath):
    """自动分割并生成动画"""
    img = Image.open(filepath).convert("RGBA")
    w, h = img.size
    if debug:
        print(f"\n处理文件: {filepath}, 尺寸: {w}x{h}")

    rows = detect_max_rows(img, max_rows, alpha_threshold)
    cols = detect_max_cols(img, max_cols, alpha_threshold, rows)

    if debug:
        print(f"自动分割结果: {cols} 列 x {rows} 行")

    # 检查是否无法自动分割（行或列为1）
    if rows == 1 or cols == 1:
        if debug:
            print(f"⚠️ 自动分割结果不理想（{cols}列×{rows}行），需要手动分割")
        return False, rows, cols

    frame_w = w // cols
    frame_h = h // rows

    frames = []
    for y in range(rows):
        for x in range(cols):
            box = (x * frame_w, y * frame_h, (x + 1) * frame_w, (y + 1) * frame_h)
            frame = img.crop(box)
            arr = np.array(frame)
            if np.all(arr[..., 3] == 0):  # 跳过完全透明帧
                continue
            frames.append(frame)

    if not frames:
        print(f"⚠️ 跳过 {os.path.basename(filepath)}（无有效帧）")
        return False, rows, cols

    duration = int(1000 / fps)
    filename = os.path.splitext(os.path.basename(filepath))[0]
    outpath = os.path.join(output_folder, f"{filename}.{'webp' if format == 'webp' else 'png'}")

    if format == "webp":
        frames[0].save(
            outpath,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,
            disposal=2,
            lossless=True
        )
    else:
        # 对于APNG格式，这里简化处理
        frames[0].save(
            outpath,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0
        )

    print(f"✅ {filename}: {cols}x{rows} 网格 → {len(frames)}帧，{fps}fps → {outpath}")
    return True, rows, cols


class ManualImageSplitter:
    def __init__(self, input_folder, output_folder):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.image_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.png')]
        self.current_index = 0
        self.rows = 1
        self.cols = 1
        self.original_image = None
        self.preview_image = None
        self.scaled_preview = None
        self.scale_factor = 1.0
        self.screen = None
        self.font = None

    def load_current_image(self):
        if self.current_index >= len(self.image_files):
            return False

        filepath = os.path.join(self.input_folder, self.image_files[self.current_index])
        self.original_image = Image.open(filepath).convert("RGBA")
        self.update_preview()
        return True

    def calculate_scale_factor(self, img_size):
        """计算缩放比例以适应预览窗口"""
        img_width, img_height = img_size
        max_width, max_height = preview_max_size

        scale_x = max_width / img_width
        scale_y = max_height / img_height
        self.scale_factor = min(scale_x, scale_y, 1.0)  # 不超过原图大小

        return self.scale_factor

    def update_preview(self):
        """根据当前行列数更新预览图像"""
        if self.original_image is None:
            return

        w, h = self.original_image.size

        # 计算缩放比例
        self.calculate_scale_factor((w, h))
        scaled_w = int(w * self.scale_factor)
        scaled_h = int(h * self.scale_factor)

        # 创建带网格线的预览图像
        preview = self.original_image.copy()

        # 转换为Pygame可用的格式
        preview_rgb = preview.convert("RGB")
        preview_surface = pygame.image.fromstring(preview_rgb.tobytes(), preview_rgb.size, preview_rgb.mode)

        # 绘制网格线到原尺寸图像
        grid_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        frame_w = w // self.cols
        frame_h = h // self.rows

        for i in range(1, self.rows):
            pygame.draw.line(grid_surface, (255, 0, 0, 128), (0, i * frame_h), (w, i * frame_h), 2)
        for j in range(1, self.cols):
            pygame.draw.line(grid_surface, (255, 0, 0, 128), (j * frame_w, 0), (j * frame_w, h), 2)

        # 将网格线合成到预览图像上
        preview_surface.blit(grid_surface, (0, 0))

        # 缩放预览图像
        self.scaled_preview = pygame.transform.smoothscale(preview_surface, (scaled_w, scaled_h))

    def get_display_rect(self, screen_width, screen_height):
        """获取图像在窗口中的显示位置（居中显示）"""
        if self.scaled_preview is None:
            return pygame.Rect(0, 0, 0, 0)

        info_height = 80  # 信息区域高度

        scaled_width, scaled_height = self.scaled_preview.get_size()
        x = (screen_width - scaled_width) // 2
        y = (screen_height - info_height - scaled_height) // 2

        return pygame.Rect(x, y, scaled_width, scaled_height)

    def calculate_window_size(self):
        """计算适合的窗口大小"""
        if self.scaled_preview is None:
            return preview_max_size[0], preview_max_size[1] + 80

        scaled_width, scaled_height = self.scaled_preview.get_size()
        window_width = min(max(scaled_width, 800), preview_max_size[0])
        window_height = scaled_height + 80

        return window_width, window_height

    def save_animation(self):
        """保存动画文件"""
        if self.original_image is None:
            return False

        w, h = self.original_image.size
        frame_w = w // self.cols
        frame_h = h // self.rows

        frames = []
        for y in range(self.rows):
            for x in range(self.cols):
                box = (x * frame_w, y * frame_h, (x + 1) * frame_w, (y + 1) * frame_h)
                frame = self.original_image.crop(box)
                arr = np.array(frame)
                if np.all(arr[..., 3] == 0):  # 跳过完全透明帧
                    continue
                frames.append(frame)

        if not frames:
            print(f"⚠️ 跳过 {self.image_files[self.current_index]}（无有效帧）")
            return False

        duration = int(1000 / fps)
        filename = os.path.splitext(self.image_files[self.current_index])[0]
        outpath = os.path.join(self.output_folder, f"{filename}.{'webp' if format == 'webp' else 'png'}")

        if format == "webp":
            frames[0].save(
                outpath,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0,
                disposal=2,
                lossless=True
            )
        else:
            frames[0].save(
                outpath,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0
            )

        print(f"✅ {filename}: {self.cols}x{self.rows} 网格 → {len(frames)}帧，{fps}fps → {outpath}")
        return True

    def run_manual_for_single_image(self, filepath, initial_rows=1, initial_cols=1):
        """为单个图片运行手动分割界面"""
        self.image_files = [os.path.basename(filepath)]
        self.current_index = 0
        self.rows = initial_rows
        self.cols = initial_cols

        if not self.load_current_image():
            return False

        pygame.init()

        # 计算初始窗口大小
        window_width, window_height = self.calculate_window_size()

        # 创建窗口
        self.screen = pygame.display.set_mode((window_width, window_height), pygame.RESIZABLE)
        pygame.display.set_caption(
            f"手动分割 - {self.image_files[self.current_index]} (自动分割结果: {initial_cols}×{initial_rows})")

        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        running = True
        result = False

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    result = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        if self.rows < max_rows:
                            self.rows += 1
                            self.update_preview()
                    elif event.key == pygame.K_DOWN:
                        if self.rows > 1:
                            self.rows -= 1
                            self.update_preview()
                    elif event.key == pygame.K_RIGHT:
                        if self.cols < max_cols:
                            self.cols += 1
                            self.update_preview()
                    elif event.key == pygame.K_LEFT:
                        if self.cols > 1:
                            self.cols -= 1
                            self.update_preview()
                    elif event.key == pygame.K_RETURN:
                        # 保存当前分割
                        if self.save_animation():
                            result = True
                        running = False
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                        result = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            # 绘制界面
            self.screen.fill((50, 50, 50))

            if self.scaled_preview:
                screen_width, screen_height = self.screen.get_size()
                display_rect = self.get_display_rect(screen_width, screen_height)
                self.screen.blit(self.scaled_preview, display_rect.topleft)

            screen_width, screen_height = self.screen.get_size()
            info_y = screen_height - 80

            # 控制说明
            controls = [
                "↑/↓: 调整行数",
                "←/→: 调整列数",
                "回车: 确认分割",
                "ESC: 取消"
            ]

            control_text = " | ".join(controls)
            text_surface = self.font.render(control_text, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(screen_width // 2, info_y + 20))
            self.screen.blit(text_surface, text_rect)

            # 状态信息
            status_text = f"手动分割模式 | 分割: {self.cols}×{self.rows} | 缩放: {self.scale_factor:.1%}"
            status_surface = self.small_font.render(status_text, True, (200, 200, 200))
            status_rect = status_surface.get_rect(center=(screen_width // 2, info_y + 50))
            self.screen.blit(status_surface, status_rect)

            if self.original_image:
                orig_w, orig_h = self.original_image.size
                size_text = f"原图尺寸: {orig_w}×{orig_h} | 每帧尺寸: {orig_w // self.cols}×{orig_h // self.rows}"
                size_surface = self.small_font.render(size_text, True, (180, 180, 255))
                size_rect = size_surface.get_rect(center=(screen_width // 2, info_y + 75))
                self.screen.blit(size_surface, size_rect)

            pygame.display.flip()

        pygame.quit()
        return result


def process_all_images():
    """批量处理所有图片"""
    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.png')]
    manual_splitter = ManualImageSplitter(input_folder, output_folder)

    for i, filename in enumerate(image_files):
        filepath = os.path.join(input_folder, filename)
        print(f"\n处理 {i + 1}/{len(image_files)}: {filename}")

        # 先尝试自动分割
        success, auto_rows, auto_cols = auto_split_and_animate(filepath)

        # 如果自动分割结果不理想（行或列为1），则启动手动分割
        if not success or auto_rows == 1 or auto_cols == 1:
            print(f"⚠️ 自动分割结果不理想（{auto_cols}列×{auto_rows}行），启动手动分割界面: {filename}")
            manual_success = manual_splitter.run_manual_for_single_image(filepath, auto_rows, auto_cols)
            if manual_success:
                print(f"✅ 手动分割完成: {filename}")
            else:
                print(f"❌ 手动分割取消: {filename}")
        else:
            print(f"✅ 自动分割完成: {filename}")


# 运行批量处理
if __name__ == "__main__":
    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹不存在: {input_folder}")
        sys.exit(1)

    process_all_images()
    print("🎬 全部处理完成。")