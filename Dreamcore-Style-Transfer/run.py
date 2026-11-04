# -*- coding: utf-8 -*-
"""
Dreamcore Style Transfer — 交互式启动脚本
将你的图片一键转换为 10 种"核"风格
"""
import sys, os

# 设置 UTF-8 输出，避免中文乱码
if sys.platform == 'win32':
    # 1. 切换终端代码页到 UTF-8
    os.system('chcp 65001 > nul 2>&1')
    # 2. 重新配置 stdout 编码
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    # 3. 设置环境变量确保子进程也用 UTF-8
    os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.image_processor import process_image, list_styles, ImageProcessor

# ============ 风格中英文映射表 ============
STYLE_NAMES = {
    "dreamcore":          "经典梦核 (Dreamcore)",
    "weirdcore":          "怪核 (Weirdcore)",
    "liminal_space":      "阈限空间 (Liminal Space)",
    "traumacore":         "伤核 (Traumacore)",
    "backrooms":          "后室 (Backrooms)",
    "kidcore":            "童年核 (Kidcore)",
    "poolcore":           "池核 (Poolcore)",
    "webcore":            "网核 (Webcore)",
    "hypnocore":          "催眠核 (Hypnocore)",
    "chinese_dreamcore":  "中式梦核 (Chinese Dreamcore)",
}

STYLE_EMOJIS = {
    "dreamcore":          "🌀",
    "weirdcore":          "👁️",
    "liminal_space":      "🚪",
    "traumacore":         "💔",
    "backrooms":          "🟨",
    "kidcore":            "🌈",
    "poolcore":           "🏊",
    "webcore":            "💾",
    "hypnocore":          "🌀",
    "chinese_dreamcore":  "📺",
}

INTENSITY_INFO = {
    "mild":    "若有若无的风格暗示（参数 ×0.5）",
    "standard": "标准风格效果（推荐）",
    "extreme": "极致力度的风格渲染（参数 ×1.5）",
}


def clear_screen():
    os.system('cls' if sys.platform == 'win32' else 'clear')


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║          🎨  Dreamcore Style Transfer                ║
║           梦核风格图像处理器  v2.0                     ║
║       10 种"核"风格 | 纯 Pillow 像素级渲染             ║
╚══════════════════════════════════════════════════════╝
""")


def print_styles():
    """显示所有可用风格"""
    styles = list_styles()
    print("┌────┬─────────────────────────────────────┐")
    print("│  # │  风格名称                           │")
    print("├────┼─────────────────────────────────────┤")
    for i, s in enumerate(styles, 1):
        emoji = STYLE_EMOJIS.get(s['id'], '🎨')
        name = STYLE_NAMES.get(s['id'], s['name'])
        print(f"│ {i:2d} │ {emoji} {name:<32s} │")
    print("└────┴─────────────────────────────────────┘")


def get_image_path():
    """获取输入图片路径"""
    while True:
        print("\n📷 请输入图片路径（支持 JPG/PNG/WEBP/BMP/GIF）：")
        path = input("   > ").strip().strip('"').strip("'")
        if not path:
            print("   ⚠️  路径不能为空，请重试")
            continue
        if not os.path.exists(path):
            print(f"   ⚠️  文件不存在: {path}")
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'):
            print(f"   ⚠️  不支持的格式: {ext}，支持 JPG/PNG/WEBP/BMP/GIF")
            continue
        return path


def get_style():
    """选择风格"""
    styles = list_styles()
    while True:
        print("\n🎨 请选择风格（输入编号 1-10）：")
        choice = input("   > ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(styles):
            s = styles[int(choice) - 1]
            name = STYLE_NAMES.get(s['id'], s['name'])
            print(f"   ✅ 已选择: {name}")
            return s['id']
        print(f"   ⚠️  请输入 1-{len(styles)} 之间的数字")


def get_intensity():
    """选择强度"""
    while True:
        print("\n🔥 请选择风格强度：")
        print(f"   1. 轻度   (mild)    — {INTENSITY_INFO['mild']}")
        print(f"   2. 标准   (standard)— {INTENSITY_INFO['standard']}")
        print(f"   3. 极致   (extreme)— {INTENSITY_INFO['extreme']}")
        choice = input("   > ").strip()
        if choice == '1':
            return 'mild'
        elif choice == '2':
            return 'standard'
        elif choice == '3':
            return 'extreme'
        print("   ⚠️  请输入 1、2 或 3")


def get_output_path(input_path, style_id, intensity):
    """生成输出路径"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(base_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    default_name = f"{base_name}_{style_id}_{intensity}.jpg"
    default_path = os.path.join(base_dir, default_name)

    print(f"\n💾 输出路径（回车使用默认）：")
    print(f"   默认: {default_path}")
    custom = input("   > ").strip().strip('"').strip("'")
    return custom if custom else default_path


def process_with_progress(input_path, style_id, intensity, output_path):
    """带进度提示的处理"""
    style_name = STYLE_NAMES.get(style_id, style_id)
    emoji = STYLE_EMOJIS.get(style_id, '🎨')

    print(f"\n{'='*50}")
    print(f"  {emoji} 正在处理: {style_name}")
    print(f"  强度: {intensity}")
    print(f"  输入: {os.path.basename(input_path)}")
    print(f"{'='*50}")

    print("  Stage 1/5: 色彩分级...")
    print("  Stage 2/5: 曝光调整...")
    print("  Stage 3/5: 颗粒噪点...")
    print("  Stage 4/5: 柔光Bloom...")
    print("  Stage 5/5: 扭曲特效...")

    result = process_image(input_path, style_id, intensity, output_path)

    size_kb = os.path.getsize(result) / 1024
    if size_kb > 1024:
        size_str = f"{size_kb / 1024:.1f} MB"
    else:
        size_str = f"{size_kb:.1f} KB"

    print(f"\n  ✅ 处理完成!")
    print(f"  📁 输出文件: {result}")
    print(f"  📏 文件大小: {size_str}")
    print(f"{'='*50}")
    return result


def ask_continue():
    """询问是否继续"""
    print()
    while True:
        choice = input("🔄 还要继续处理吗？(y/n) > ").strip().lower()
        if choice in ('y', 'yes'):
            return True
        elif choice in ('n', 'no', 'q'):
            return False
        print("   ⚠️  请输入 y (继续) 或 n (退出)")


def main():
    clear_screen()
    print_banner()
    print_styles()

    while True:
        # Step 1: 选择图片
        image_path = get_image_path()

        # Step 2: 选择风格
        style_id = get_style()

        # Step 3: 选择强度
        intensity = get_intensity()

        # Step 4: 确认输出路径
        output_path = get_output_path(image_path, style_id, intensity)

        # Step 5: 处理
        try:
            process_with_progress(image_path, style_id, intensity, output_path)
        except Exception as e:
            print(f"\n   ❌ 处理失败: {e}")
            print("   请检查图片是否完整，或尝试其他图片")

        # Step 6: 是否继续
        if not ask_continue():
            break

    print("\n👋 感谢使用 Dreamcore Style Transfer！下次见~\n")


if __name__ == '__main__':
    main()
