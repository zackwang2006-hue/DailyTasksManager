from PIL import Image, ImageDraw
from pathlib import Path

# 原图路径，按你的实际文件名修改
SOURCE = Path("assets/icons/source.png")

# 输出目录
OUT_DIR = Path("assets/icons/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SIZES = [16, 24, 32, 48, 64, 128, 256]


def crop_center_square(img: Image.Image) -> Image.Image:
    """居中裁剪为正方形"""
    w, h = img.size
    side = min(w, h)

    left = (w - side) // 2
    top = (h - side) // 2
    right = left + side
    bottom = top + side

    return img.crop((left, top, right, bottom))


def apply_rounded_alpha(img: Image.Image, radius_ratio: float = 0.18) -> Image.Image:
    """给图片添加真正的透明圆角"""
    img = img.convert("RGBA")
    w, h = img.size

    radius = int(min(w, h) * radius_ratio)

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, w, h),
        radius=radius,
        fill=255
    )

    img.putalpha(mask)
    return img


def main():
    img = Image.open(SOURCE).convert("RGBA")

    # 先裁成正方形
    img = crop_center_square(img)

    # 先在大图上做透明圆角
    img = apply_rounded_alpha(img, radius_ratio=0.18)

    png_paths = []

    for size in SIZES:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        out_path = OUT_DIR / f"icon_{size}x{size}.png"
        resized.save(out_path)
        png_paths.append(out_path)

    # 用最大尺寸图合成 ico，并把多尺寸一起塞进去
    ico_path = OUT_DIR / "app.ico"

    base = Image.open(png_paths[-1]).convert("RGBA")
    base.save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES]
    )

    print("生成完成：")
    for p in png_paths:
        print(p)
    print(ico_path)


if __name__ == "__main__":
    main()