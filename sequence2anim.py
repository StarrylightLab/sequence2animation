import os
import numpy as np
from PIL import Image

# ========== 可调参数 ==========
input_folder = "/Users/nayuchuanmei/Documents/[需要处理的]"      # 输入文件夹路径
output_folder = "output"       # 输出文件夹路径
fps = 12                       # 动画帧率
format = "webp"                # 可选 "webp" 或 "apng"
alpha_threshold = 28          # alpha 阈值 (0-255)
max_rows = 20                  # 最大行分割数
max_cols = 20                  # 最大列分割数
debug = True                   # 是否打印调试信息
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
            top = arr[i*frame_h, :, 3]
            bottom = arr[(i+1)*frame_h-1, :, 3]
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
            left = arr[:, j*frame_w, 3]
            right = arr[:, (j+1)*frame_w-1, 3]
            for i in range(rows):
                slice_top = i * (h // rows)
                slice_bottom = (i+1) * (h // rows)
                if np.any(left[slice_top:slice_bottom] >= alpha_threshold) or np.any(right[slice_top:slice_bottom] >= alpha_threshold):
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

def split_and_animate(filepath):
    img = Image.open(filepath).convert("RGBA")
    w, h = img.size
    if debug:
        print(f"\n处理文件: {filepath}, 尺寸: {w}x{h}")

    rows = detect_max_rows(img, max_rows, alpha_threshold)
    cols = detect_max_cols(img, max_cols, alpha_threshold, rows)

    if debug:
        print(f"最终分割结果: {cols} 列 x {rows} 行")

    frame_w = w // cols
    frame_h = h // rows

    frames = []
    for y in range(rows):
        for x in range(cols):
            box = (x*frame_w, y*frame_h, (x+1)*frame_w, (y+1)*frame_h)
            frame = img.crop(box)
            arr = np.array(frame)
            if np.all(arr[..., 3] == 0):  # 跳过完全透明帧
                continue
            frames.append(frame)

    if not frames:
        print(f"⚠️ 跳过 {os.path.basename(filepath)}（无有效帧）")
        return

    duration = int(1000 / fps)
    filename = os.path.splitext(os.path.basename(filepath))[0]
    outpath = os.path.join(output_folder, f"{filename}.{ 'webp' if format=='webp' else 'png' }")

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
        from apng import APNG
        temp_files = []
        for idx, f in enumerate(frames):
            tmp = os.path.join(output_folder, f"tmp_{idx}.png")
            f.save(tmp)
            temp_files.append(tmp)
        apng = APNG()
        for f in temp_files:
            apng.append_file(f, delay=duration)
        apng.save(outpath)
        for f in temp_files:
            os.remove(f)

    print(f"✅ {filename}: {cols}x{rows} 网格 → {len(frames)}帧，{fps}fps → {outpath}")

# 批量处理
for file in os.listdir(input_folder):
    if file.lower().endswith(".png"):
        split_and_animate(os.path.join(input_folder, file))

print("🎬 全部处理完成。")
