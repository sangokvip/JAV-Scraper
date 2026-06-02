import os
from PIL import Image

def main():
    orig_path = "app_icon_orig.png"
    if not os.path.exists(orig_path):
        print(f"Error: {orig_path} not found.")
        return
    
    img = Image.open(orig_path)
    
    # 确保保存的文件夹存在
    os.makedirs("gui", exist_ok=True)
    
    # 1. 存为 gui/icon.png (256x256)
    img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
    img_resized.save("gui/icon.png", format="PNG")
    print("Generated gui/icon.png")
    
    # 2. 存为 icon.ico (Windows 多尺寸图标，包括 16x16, 32x32, 48x48, 64x64, 128x128, 256x256)
    img.save("icon.ico", format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print("Generated icon.ico")
    
    # 3. 存为 icon.icns (macOS 专属图标包)
    # pillow 对 icns 格式同样支持直接保存
    img.save("icon.icns", format="ICNS")
    print("Generated icon.icns")

if __name__ == "__main__":
    main()
