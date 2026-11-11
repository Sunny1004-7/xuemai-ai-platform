"""从有限状态序列制作原创Python教学短片，无网络与任意代码执行。"""
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
SCENES=[
 ('python-loop','Python：循环与累加','循环与条件',['total = 0','for value in [2, 4, 6]:','    total += value','print(total)'],[
  ('初始状态',{'total':'0','value':'未绑定'},'初始累加器为0，还没有处理元素。',0),
  ('第一次迭代',{'total':'2','value':'2'},'先绑定value=2，再将total从0更新为2。',2),
  ('第二次迭代',{'total':'6','value':'4'},'total保持已处理元素之和，2+4得到6。',2),
  ('第三次迭代',{'total':'12','value':'6'},'处理第三项后total为12，循环不变量继续成立。',2),
  ('循环结束',{'total':'12','输出':'12'},'没有下一个元素时退出循环，随后打印12。',3),
  ('边界检查',{'输入':'[]','total':'0'},'空列表没有迭代，初始值0直接作为结果。',0)]),
 ('python-list','Python：列表切片与共享引用','列表切片与别名',['a = [1, 2]','b = a','c = a[:]','b.append(3)'],[
  ('创建列表',{'a':'[1, 2]'},'a绑定一个包含1和2的列表对象。',0),
  ('引用赋值',{'a':'[1, 2]','b':'与a共享对象'},'b=a不会复制列表，两个变量引用同一对象。',1),
  ('切片复制',{'a':'[1, 2]','b':'与a共享对象','c':'[1, 2] 独立外层列表'},'a[:]创建新的外层列表，c与a不共享外层容器。',2),
  ('追加元素',{'a':'[1, 2, 3]','b':'[1, 2, 3]','c':'[1, 2]'},'通过b修改共享对象，a随之变化，c保持不变。',3),
  ('迁移检查',{'嵌套列表':'浅拷贝仍共享内部对象'},'如果元素本身是列表，浅拷贝仍共享内部对象。',2)]),
 ('python-function','Python：函数参数与局部状态','参数绑定',['def add(a, b=2):','    result = a + b','    return result','value = add(3)'],[
  ('定义函数',{'默认b':'2'},'定义时保存默认值，调用时绑定参数。',0),
  ('调用并绑定',{'局部a':'3','局部b':'2'},'add(3)将3绑定给a，b使用默认值2。',3),
  ('局部计算',{'局部a':'3','局部b':'2','局部result':'5'},'函数内部计算result=5，局部名称只属于本次调用。',1),
  ('返回结果',{'返回值':'5','外部value':'5'},'return结束调用，返回值绑定给外部value。',2),
  ('关键字参数',{'调用':'add(3,b=4)','返回值':'7'},'关键字参数按名称匹配，此时b为4，结果为7。',0),
  ('独立检查',{'调用':'add(0)','返回值':'2'},'代入新输入0，逐步验证默认参数与返回值。',3)])]

def main():
    media=ROOT/'backend/media'; media.mkdir(exist_ok=True)
    regular=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',26)
    heading=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',36)
    codefont=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',29)
    metadata=[]
    for slug,title,kid,code,states in SCENES:
        duration=36;fps=12;output=media/(slug+'.mp4')
        process=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
        for frame in range(duration*fps):
            step=min(len(states)-1,frame*len(states)//(duration*fps));label,variables,caption,line=states[step]
            img=Image.new('RGB',(1280,720),'#F1F0E8');d=ImageDraw.Draw(img)
            d.text((65,42),title,font=heading,fill='#263A37');d.line((65,105,1215,105),fill='#2E6A67',width=2)
            d.text((65,133),f'{step+1:02d} / {len(states):02d}   {label}',font=regular,fill='#52665F')
            d.rounded_rectangle((65,205,710,540),radius=16,fill='#FDFCF8')
            for i,text in enumerate(code):
                if i==line:d.rounded_rectangle((85,240+i*58,690,290+i*58),radius=7,fill='#D7E6DB')
                d.text((104,248+i*58),text,font=codefont,fill='#263A37')
            d.text((760,208),'当前状态',font=regular,fill='#2E6A67')
            for i,(name,value) in enumerate(variables.items()):
                d.text((760,266+i*76),name,font=regular,fill='#52665F');d.text((760,298+i*76),value,font=regular,fill='#263A37')
            d.rectangle((0,601,1280,720),fill='#FDFCF8');d.text((65,636),caption,font=regular,fill='#263A37')
            d.rectangle((65,699,65+1150*(frame+1)/(duration*fps),702),fill='#2E6A67')
            process.stdin.write(img.tobytes())
        process.stdin.close()
        if process.wait():raise RuntimeError('Python教学视频生成失败')
        subtitles=[{'start':round(i*duration/len(states),2),'end':round((i+1)*duration/len(states),2),'text':s[2]} for i,s in enumerate(states)]
        metadata.append({'slug':slug,'title':title,'knowledge_title':kid,'duration':duration,'subtitles':subtitles,'synthetic':True})
        print(title,output.stat().st_size)
    (media/'python-teaching-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
