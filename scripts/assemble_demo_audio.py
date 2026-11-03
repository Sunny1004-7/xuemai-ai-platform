"""把本机合成旁白按实际录制时间轴合入视频，生成可核查的交付媒体元数据。"""
import json
from pathlib import Path
import subprocess
import wave
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]


def build():
    source=ROOT/'最终参赛提交材料/学脉XueMai-演示视频.mp4'
    target=ROOT/'最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4'
    scenes=json.loads((ROOT/'scripts/demo-scenes.json').read_text(encoding='utf-8-sig'))
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',str(source)]
    filters=[];voices=[]
    for index,scene in enumerate(scenes,1):
        audio=ROOT/scene['file']
        with wave.open(str(audio)) as wav:
            seconds=wav.getnframes()/wav.getframerate()
            if seconds>scene['duration']+.1:raise RuntimeError('旁白超过场景时长：'+scene['id'])
        command+=['-i',str(audio)]
        delay=int(scene['start']*1000)
        filters.append(f'[{index}:a]adelay={delay}:all=1[a{index}]')
        voices.append(f'[a{index}]')
    filters.append(''.join(voices)+f'amix=inputs={len(scenes)}:duration=longest:normalize=0[aout]')
    command+=['-filter_complex',';'.join(filters),'-map','0:v','-map','[aout]','-c:v','copy','-c:a','aac','-b:a','128k','-t','395','-movflags','+faststart',str(target)]
    subprocess.run(command,check=True)
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(target)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    record={'output':target.name,'planned_seconds':395,'resolution':'1920x1080','development_record_replay_seconds':135,'narration':'Microsoft Huihui Desktop，离线合成语音','real_api_calls_during_recording':0,'inspection':probe.stderr}
    (ROOT/'最终参赛提交材料/视频验收记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='inspection'},ensure_ascii=False))
    print(probe.stderr)


if __name__=='__main__':build()
