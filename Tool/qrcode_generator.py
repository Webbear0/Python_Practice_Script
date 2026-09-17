# ============================================================
# 神奇的二维码 —— 二维码生成器
# 功能：输入任意文字或网址，点击按钮生成对应的二维码图片
# 需要安装：pip install Pillow qrcode
# ============================================================

# ---------- 第一步：导入所需的库 ----------
# tkinter 是 Python 自带的图形界面库，用来创建窗口、按钮等
from tkinter import *

# PIL（Pillow）是第三方图片处理库
# Image 用于打开和处理图片
from PIL import Image
# ImageTk 用于将图片转成 tkinter 能显示的格式
from PIL import ImageTk

# qrcode 是第三方二维码生成库
import qrcode

# os 用于创建文件夹（存放二维码图片）
import os


# ---------- 第二步：创建保存二维码的文件夹 ----------
# 在当前目录下创建 qrcode_output 文件夹
save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qrcode_output')
# exist_ok=True 表示如果文件夹已存在就不报错
if not os.path.exists(save_dir):
    os.makedirs(save_dir)


# ---------- 第三步：创建主窗口（画板） ----------
root = Tk()
# 设置窗口标题
root.title('二维码生成器')
# 设置窗口大小：宽500×高600，距屏幕左边300像素，距顶部100像素
root.geometry('500x600+300+100')


# ---------- 第四步：创建输入框 ----------
# Entry 是文本输入框控件，width=60 设置宽度为60个字符
entry = Entry(root, width=60)
# grid 布局：放在第0行第0列
entry.grid(row=0, column=0, padx=5, pady=5)


# ---------- 第五步：定义回调函数（点击按钮时执行的任务） ----------
def callback():
    """
    回调函数：获取输入框内容 → 生成二维码 → 显示在标签上
    """
    # 1. 获取输入框中用户输入的内容
    text_input = entry.get()

    # 如果输入为空，就不执行
    if text_input.strip() == '':
        return

    # 2. 使用 qrcode 库将输入内容生成二维码图片
    img_qr = qrcode.make(text_input)

    # 3. 构建保存路径，将二维码保存为 PNG 图片
    # 文件名使用输入内容（去掉特殊字符）
    safe_name = ''.join(c if c.isalnum() else '_' for c in text_input[:20])
    save_path = os.path.join(save_dir, safe_name + '.png')
    img_qr.save(save_path)
    print('二维码已保存到：', save_path)

    # 4. 用 Pillow 打开刚保存的二维码图片
    img_open = Image.open(save_path)
    # 调整图片大小以适应标签显示区域
    img_open = img_open.resize((400, 400))

    # 5. 将图片转换为 tkinter 能显示的格式
    img_tk = ImageTk.PhotoImage(img_open)

    # 6. 更新标签上的图片
    # configure 方法可以修改控件的属性
    label.configure(image=img_tk)
    # 关键：必须保存图片对象的引用，否则图片会被回收导致显示空白！
    label.image = img_tk


# ---------- 第六步：创建按钮 ----------
# Button 是按钮控件
# text='生成' 设置按钮文字
# command=callback 绑定点击事件（注意：不加括号！）
btn = Button(root, text='生成', command=callback)
# 放在第0行第1列（输入框的右边）
btn.grid(row=0, column=1, padx=5, pady=5)


# ---------- 第七步：创建显示二维码的标签 ----------
# Label 是标签控件，可以显示文字或图片
# 先生成一个默认的二维码作为初始显示
default_img = qrcode.make('Hello World')
default_path = os.path.join(save_dir, 'default.png')
default_img.save(default_path)
default_img = Image.open(default_path)
default_img = default_img.resize((400, 400))
default_img = ImageTk.PhotoImage(default_img)

label = Label(root, text='', image=default_img, width=450, height=450)
# 放在第1行，从第0列开始，横跨2列（columnspan=2）
label.grid(row=1, column=0, columnspan=2, pady=10)
# 保存默认图片的引用
label.image = default_img


# ---------- 第八步：启动事件循环 ----------
# mainloop() 让窗口持续显示，等待用户操作
root.mainloop()
