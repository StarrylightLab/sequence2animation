import os
import numpy as np
from PIL import Image
import pygame
import sys

# ========== 可调参数 ==========
input_folder = "/Users/nayuchuanmei/Documents/剪映贴纸"  # 输入文件夹路径
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


class ImageSplitter:
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
        self.finished = False  # 添加完成标志

    def load_current_image(self):
        if self.current_index >= len(self.image_files):
            self.finished = True
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
        window_width = min(max(scaled_width, 800), preview_max_size[0])  # 最小800，最大preview_max_size[0]
        window_height = scaled_height + 80  # 加上信息区域的高度

        return window_width, window_height

    def save_animation(self):
        """保存动画文件"""
        if self.original_image is None:
            return

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
            return

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
            # 对于APNG格式，这里简化处理，实际使用时需要安装apng库
            frames[0].save(
                outpath,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0
            )

        print(f"✅ {filename}: {self.cols}x{self.rows} 网格 → {len(frames)}帧，{fps}fps → {outpath}")

    def next_image(self):
        """切换到下一张图片"""
        self.current_index += 1
        self.rows = 1
        self.cols = 1
        if self.current_index < len(self.image_files):
            self.load_current_image()
            return True
        else:
            self.finished = True
            return False

    def run(self):
        """运行可视化界面"""
        pygame.init()

        # 获取第一张图片
        if not self.load_current_image():
            print("没有找到PNG图片")
            return

        # 计算初始窗口大小
        window_width, window_height = self.calculate_window_size()

        # 创建窗口
        self.screen = pygame.display.set_mode((window_width, window_height), pygame.RESIZABLE)
        pygame.display.set_caption(f"图片分割工具 - {self.image_files[self.current_index]}")

        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.finished:
                        running = False
                        continue

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
                        # 保存当前分割并切换到下一张图片
                        self.save_animation()
                        if not self.next_image():
                            # 所有图片处理完成
                            if debug:
                                print("所有图片处理完成，按任意键退出...")
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                elif event.type == pygame.VIDEORESIZE:
                    # 处理窗口大小调整
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            # 绘制界面
            self.screen.fill((50, 50, 50))  # 灰色背景

            if self.finished:
                # 显示完成信息
                completion_text = "All image processing completed! Press ESC to exit"
                text_surface = self.font.render(completion_text, True, (255, 255, 255))
                text_rect = text_surface.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2))
                self.screen.blit(text_surface, text_rect)
            else:
                # 绘制预览图像（居中显示）
                if self.scaled_preview:
                    screen_width, screen_height = self.screen.get_size()
                    display_rect = self.get_display_rect(screen_width, screen_height)
                    self.screen.blit(self.scaled_preview, display_rect.topleft)

                # 绘制控制信息
                screen_width, screen_height = self.screen.get_size()
                info_y = screen_height - 80

                # 第一行：控制说明
                controls = [
                    "↑/↓: Adjust Rows",
                    "←/→: Adjust Columns",
                    "回车: Confirm Cut",
                    "ESC: Exit"
                ]

                control_text = " | ".join(controls)
                text_surface = self.font.render(control_text, True, (255, 255, 255))
                text_rect = text_surface.get_rect(center=(screen_width//2, info_y + 20))
                self.screen.blit(text_surface, text_rect)

                # 第二行：当前状态
                status_text = f"Iamge: {self.current_index + 1}/{len(self.image_files)} | FileName: {self.image_files[self.current_index]} | Splitting: {self.cols}×{self.rows} | Scale: {self.scale_factor:.1%}"
                status_surface = self.small_font.render(status_text, True, (200, 200, 200))
                status_rect = status_surface.get_rect(center=(screen_width//2, info_y + 50))
                self.screen.blit(status_surface, status_rect)

                # 第三行：原图尺寸信息
                if self.original_image:
                    orig_w, orig_h = self.original_image.size
                    size_text = f"Orig_Size: {orig_w}×{orig_h} | Frame_Size: {orig_w//self.cols}×{orig_h//self.rows}"
                    size_surface = self.small_font.render(size_text, True, (180, 180, 255))
                    size_rect = size_surface.get_rect(center=(screen_width//2, info_y + 75))
                    self.screen.blit(size_surface, size_rect)

            pygame.display.flip()

        pygame.quit()
        print("🎬 All Done。")


# 运行可视化界面
if __name__ == "__main__":
    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹不存在: {input_folder}")
        sys.exit(1)

    splitter = ImageSplitter(input_folder, output_folder)
    if not splitter.image_files:
        print(f"在 {input_folder} 中没有找到PNG图片")
        sys.exit(1)

    splitter.run()