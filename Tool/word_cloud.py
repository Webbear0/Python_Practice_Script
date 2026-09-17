#coding=utf-8
# 功能: 提取关键字，生成词云


import jieba.posseg as pseg
import wordcloud,tkinter
from PIL import Image, ImageTk

def word_cloud(file_name, font_name, img_width, img_height):
    with open(f'{file_name}', encoding='utf-8') as file:
        text_content = file.read()
    wtimes = {}
    cstr = []
    sw = []

    wlist = pseg.lcut(text_content)
    for a in wlist:
        if a.flag == 'nr':
            wtimes[a.word] = wtimes.get(a.word, 0) + 1
            cstr.append(a.word)
        else:
            sw.append(a.word)
    # 提取关键字
    wlist = list(wtimes.keys())
    wlist.sort(key=lambda x: wtimes[x], reverse=True)
    for a in wlist[:10]:
        print(a, wtimes[a], sep='\t')
    text = ' '.join(cstr)
    # 生成图片文件
    cloud = wordcloud.WordCloud(font_path=font_name, background_color='white'
                                , stopwords=sw, collocations=False
                                , width=img_width, height=img_height).generate(text)

    file = cloud.to_file(f'{file_name}.jpg')
    root = tkinter.Tk()
    img = Image.open(f'{file_name}.jpg')
    pic = ImageTk.PhotoImage(img)
    imgLabel = tkinter.Label(root, image=pic)
    imgLabel.pack()
    root.mainloop()

if __name__ == "__main__":
    print("词云系统\n")
    # 使用前请将txt格式文档与ttc格式字体保存到程序目录中
    file_name = input('请输入需要转换的文档名:')
    font_name = input('请输入字体的文件名:')
    img_width = int(input('请输入转换的图片宽度:'))
    img_height = int(input('请输入转换的图片高度:'))
    word_cloud(file_name, font_name, img_width, img_height)