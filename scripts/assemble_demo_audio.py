"""按逐句时间轴合入配音和底部字幕，输出1080p正式演示。"""
import json
from pathlib import Path
import hashlib
import re
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def ass_time(t):
    cs=round(t*100);return f'{cs//360000:01}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def inspect_output(target, segments):
    """完整解码并保留可公开的媒体检查结果，不写入本机路径。"""
    probe=subprocess.run([FFMPEG,'-hide_banner','-i',str(target),'-af','volumedetect','-f','null','-'],capture_output=True,text=True,encoding='utf8',errors='replace',check=True)
    (ROOT/'.local/video-full-decode-volume.log').write_text(probe.stderr,encoding='utf8')
    duration_match=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe.stderr)
    video_match=re.search(r'Video: h264[^\n]*?\b(\d{3,5})x(\d{3,5})\b[^\n]*?([\d.]+) fps',probe.stderr)
    if not duration_match or not video_match or 'Audio: aac' not in probe.stderr:
        raise RuntimeError('输出媒体流信息不符合H.264/AAC要求')
    hours,minutes,seconds=map(float,duration_match.groups())
    duration=hours*3600+minutes*60+seconds
    width,height,fps=map(float,video_match.groups())
    if abs(duration-450)>.1 or (width,height,fps)!=(1920,1080,24):
        raise RuntimeError('输出片长、分辨率或帧率不符合预期')
    mean=float(re.search(r'mean_volume: ([\-\d.]+) dB',probe.stderr)[1])
    peak=float(re.search(r'max_volume: ([\-\d.]+) dB',probe.stderr)[1])
    if mean <= -40 or peak >= 0:raise RuntimeError('音轨静音或达到削波峰值，请检查混音')
    for left,right in zip(segments,segments[1:]):
        if left['start']+left['duration']>right['start']+.005:raise RuntimeError('配音分句时间重叠')
    if segments[-1]['start']+segments[-1]['duration']>450:raise RuntimeError('配音超过片长')
    record={'output':target.name,'duration_seconds':duration,'resolution':f'{int(width)}x{int(height)}','fps':fps,
            'video_codec':'H.264','audio_codec':'AAC','full_decode_passed':True,
            'development_record_replay_seconds':120,'development_records_dates':['2026-11-03'],
            'narration':'晓晓中文神经合成语音','narration_segments':len(segments),
            'narration_timeline_no_overlap':True,'subtitle_timing':'同次TTS WordBoundary经音频速度换算','audio_mean_db':mean,'audio_peak_db':peak,
            'audio_auditory_review':'未进行人工听审，已验证音轨非静音、分句时间轴和完整解码',
            'subtitles_burned_in':True,'subtitle_entries':len((ROOT/'最终参赛提交材料/学脉XueMai-演示字幕.srt').read_text(encoding='utf8').strip().split('\n\n')),
            'real_api_calls_during_recording':0,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    encoded=json.dumps(record,ensure_ascii=False,indent=2)
    (ROOT/'最终参赛提交材料/视频验收记录.json').write_text(encoded,encoding='utf8')
    (ROOT/'docs/demo').mkdir(exist_ok=True)
    (ROOT/'docs/demo/验收结果.json').write_text(encoded,encoding='utf8')
    return record

def build():
    local=ROOT/'.local/narration'
    segments=json.loads((local/'segments.json').read_text(encoding='utf8'))
    source=ROOT/'最终参赛提交材料/学脉XueMai-演示视频.mp4'
    target=ROOT/'最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4'
    groups=[]
    for start in range(0,len(segments),12):
        command=[FFMPEG,'-y','-loglevel','error']
        batch=segments[start:start+12]
        for s in batch:command+=['-i',str(ROOT/s['file'])]
        filters=[f'[{i}:a]adelay={round(s["start"]*1000)}:all=1[a{i}]' for i,s in enumerate(batch)]
        filters.append(''.join(f'[a{i}]' for i in range(len(batch)))+f'amix=inputs={len(batch)}:duration=longest:normalize=0[out]')
        output=local/f'group-{start//12}.wav'
        command+=['-filter_complex',';'.join(filters),'-map','[out]','-ar','24000',str(output)]
        subprocess.run(command,check=True);groups.append(output)
    command=[FFMPEG,'-y','-loglevel','error']
    for group in groups:command+=['-i',str(group)]
    # 有界补齐并在输出侧再次限制时长，避免空白尾音成为无限音源。
    command+=['-filter_complex',f'amix=inputs={len(groups)}:normalize=0,apad=whole_dur=450,atrim=duration=450[out]',
              '-map','[out]','-ar','24000','-t','450',str(local/'complete.wav')]
    subprocess.run(command,check=True)
    srt=(ROOT/'最终参赛提交材料/学脉XueMai-演示字幕.srt').read_text(encoding='utf8')
    ass=['[Script Info]','ScriptType: v4.00+','PlayResX: 1920','PlayResY: 1080','[V4+ Styles]',
         'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
         'Style: Default,Microsoft YaHei,32,&H00FFFFFF,&H00FFFFFF,&H00372F26,&H20372F26,0,0,0,0,100,100,0,0,3,8,0,2,100,100,24,1',
         '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def seconds(s):
        h,m,v=s.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(v)
    for block in srt.strip().split('\n\n'):
        lines=block.splitlines();a,b=lines[1].split(' --> ')
        ass.append(f'Dialogue: 0,{ass_time(seconds(a))},{ass_time(seconds(b))},Default,,0,0,0,,'+''.join(lines[2:]))
    (local/'subtitles.ass').write_text('\n'.join(ass),encoding='utf8')
    subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(source),'-i',str(local/'complete.wav'),'-vf','ass=subtitles.ass','-map','0:v','-map','1:a','-c:v','libx264','-preset','fast','-crf','22','-c:a','aac','-b:a','160k','-t','450','-movflags','+faststart',str(target)],cwd=local,check=True)
    print(json.dumps(inspect_output(target,segments),ensure_ascii=False))

if __name__=='__main__':build()
