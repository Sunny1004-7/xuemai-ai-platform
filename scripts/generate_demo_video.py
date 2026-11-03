"""用真实冒泡排序状态生成自有教学视频（无外部素材、无模型调用）。"""
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]


def generate():
    frames = ROOT / '.local' / 'video-frames'
    frames.mkdir(parents=True, exist_ok=True)
    output = ROOT / 'backend' / 'media' / 'sorting-demo.mp4'
    output.parent.mkdir(parents=True, exist_ok=True)
    font_file = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_file), 35)
    small = ImageFont.truetype(str(font_file), 24)
    values = [7, 3, 8, 2, 5]
    states = [(values.copy(), -1, '观察初始序列，预测第一对比较的结果')]
    for end in range(len(values)-1, 0, -1):
        for i in range(end):
            swap = values[i] > values[i+1]
            if swap:
                values[i], values[i+1] = values[i+1], values[i]
            states.append((values.copy(), i, f'比较第 {i+1}、{i+2} 项：' + ('交换，使较大值右移' if swap else '已经有序，保留位置')))
    states.append((values.copy(), -1, '排序完成！思考：一轮结束后，哪个元素到达最终位置？'))
    fps = 10
    duration = 36
    for frame in range(duration*fps):
        index = min(len(states)-1, frame*len(states)//(duration*fps))
        vals, active, caption = states[index]
        img = Image.new('RGB', (1280,720), '#eef3fa')
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((45,38,1235,680),radius=24,fill='#ffffff')
        d.text((88,72),'学脉 · 冒泡排序：让比较变得可见',font=font,fill='#192e51')
        d.text((88,128),'数据结构与算法 / 原创合成教学演示',font=small,fill='#61718b')
        for i,v in enumerate(vals):
            x = 210+i*180
            y = 535-v*37
            d.rounded_rectangle((x,y,x+112,535),radius=12,fill='#25b69a' if i in (active,active+1) and active>=0 else '#5774da')
            d.text((x+44,y-42),str(v),font=small,fill='#192e51')
            d.text((x+30,550),str(i+1),font=small,fill='#61718b')
        d.text((88,615),caption,font=small,fill='#192e51')
        img.save(frames / f'{frame:04}.png')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
    print(f'已生成原创教学视频：36秒，1280×720，{output.stat().st_size}字节')


if __name__ == '__main__':
    generate()
