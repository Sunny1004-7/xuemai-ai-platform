"""根据实际算法步骤生成三段原创教学视频及字幕，无模型请求。"""
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
FONT='C:/Windows/Fonts/msyh.ttc'
INK='#263A37'; BRAND='#2E6A67'; SOFT='#D7E6DB'; PAPER='#F1F0E8'


def scenarios():
    values=[7,3,8,2,5]
    bubble=[(values.copy(),[],'观察初始序列，比较相邻元素。')]
    for end in range(len(values)-1,0,-1):
        for i in range(end):
            swap=values[i]>values[i+1]
            if swap:values[i],values[i+1]=values[i+1],values[i]
            bubble.append((values.copy(),[i,i+1],f'比较第{i+1}、{i+2}项，'+('交换使较大值右移。' if swap else '保持当前顺序。')))
    bubble.append((values.copy(),[],'每轮最大值归位。完全有序时，可以提前结束。'))
    stack=[]; states=[([],[],'栈是后进先出的结构，只在栈顶操作。')]
    for n in [1,2,3]:
        stack.append(n);states.append((stack.copy(),[len(stack)-1],f'将{n}压入栈顶，已有元素保持不变。'))
    for n in [3,2,1]:
        assert stack.pop()==n
        states.append((stack.copy(),[],f'弹出栈顶{n}，后进入的元素先离开。'))
    states.append(([],[],'空栈不能弹出。请区分操作顺序和数据本身的大小。'))
    ordered=[2,5,8,11,14,17,20]; lo=0;hi=len(ordered)-1; target=17
    search=[(ordered.copy(),[],'有序序列中查找17，维护闭区间的左右边界。')]
    while lo<=hi:
        mid=(lo+hi)//2
        search.append((ordered.copy(),[mid],f'区间[{lo},{hi}]，中点{mid}的值为{ordered[mid]}。'))
        if ordered[mid]==target:
            search.append((ordered.copy(),[mid],f'找到17，下标为{mid}。每次比较都缩小候选区间。'));break
        if ordered[mid]<target:lo=mid+1;action=f'目标更大，左边界更新为{lo}。'
        else:hi=mid-1;action=f'目标更小，右边界更新为{hi}。'
        search.append((ordered.copy(),list(range(lo,hi+1)),action))
    return [('sorting-demo','冒泡排序',6,bubble,36,3),('stack-demo','栈的入栈与出栈',2,states,40,1),('binary-search-demo','二分查找与边界收缩',8,search,40,5)]


def generate():
    media=ROOT/'backend/media';media.mkdir(exist_ok=True)
    font=ImageFont.truetype(FONT,42);small=ImageFont.truetype(FONT,26);number=ImageFont.truetype(FONT,38)
    metadata=[]
    for slug,title,kid,states,duration,qid in scenarios():
        output=media/(slug+'.mp4');fps=12
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
        process=subprocess.Popen(command,stdin=subprocess.PIPE)
        for frame in range(duration*fps):
            i=min(len(states)-1,frame*len(states)//(duration*fps));values,active,caption=states[i]
            img=Image.new('RGB',(1280,720),PAPER);d=ImageDraw.Draw(img)
            d.line((75,94,1205,94),fill=BRAND,width=3)
            d.text((75,45),'学脉 XueMai · '+title,font=font,fill=INK)
            d.text((75,124),f'步骤 {i+1:02d} / {len(states):02d}',font=small,fill=INK)
            if slug=='stack-demo':
                d.line((450,210,450,545,830,545,830,210),fill=BRAND,width=3)
                for index,value in enumerate(values):
                    y=485-index*84;d.rounded_rectangle((465,y,815,y+70),radius=5,fill=BRAND if index in active else SOFT)
                    d.text((620,y+8),str(value),font=number,fill='white' if index in active else INK)
                d.text((890,230),'栈顶操作',font=small,fill=INK)
            else:
                width=115;gap=26;left=(1280-len(values)*(width+gap)+gap)/2
                for index,value in enumerate(values):
                    x=left+index*(width+gap);height=value*30 if slug=='sorting-demo' else 100
                    d.rounded_rectangle((x,505-height,x+width,505),radius=7,fill=BRAND if index in active else SOFT)
                    d.text((x+36,515-height),str(value),font=number,fill='white' if index in active else INK)
                    d.text((x+40,527),str(index),font=small,fill=INK)
            d.rectangle((0,603,1280,720),fill='#FDFCF8')
            d.text((75,631),caption,font=small,fill=INK)
            d.rectangle((75,700,75+1130*(frame+1)/(duration*fps),703),fill=BRAND)
            process.stdin.write(img.tobytes())
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('教学视频编码失败')
        subtitles=[{'start':round(i*duration/len(states),2),'end':round((i+1)*duration/len(states),2),'text':state[2]} for i,state in enumerate(states)]
        metadata.append({'slug':slug,'title':title,'knowledge_id':kid,'duration':duration,'subtitles':subtitles,
                         'timeline':[{'time':s['start'],'knowledge_id':kid,'title':s['text']} for s in subtitles[::max(1,len(subtitles)//3)]],
                         'checkpoints':[{'time':round(duration*.7),'question_id':qid}],'checkpoint_question_id':qid,'synthetic':True})
        print(title,duration,output.stat().st_size)
    (media/'teaching-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':generate()
