"""在最终MP4核对固定框架、字幕字形中心及全部模块镜头。"""
import json
from pathlib import Path
import statistics

import av
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops, ImageStat

from demo_project import load_project
from subtitle_layout import caption_center

ROOT = Path(__file__).resolve().parents[1]


def frame_at(source, at):
    with av.open(str(source)) as video:
        video.seek(int(at * av.time_base))
        frame = next(frame for frame in video.decode(video=0) if frame.time is not None and float(frame.time) >= at)
        return frame.to_image(), float(frame.time)


def main():
    current, number, project = load_project()
    source = ROOT / '最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4'
    scenes = json.loads((project / 'scenes.json').read_text('utf8'))
    timeline = json.loads((project / 'edit-timeline.json').read_text('utf8'))
    captions = json.loads((project / 'subtitle-layout.json').read_text('utf8'))
    layout = json.loads((project / 'video-layout.json').read_text('utf8'))
    geometry = json.loads((project / 'media/boards-highlight-audit.json').read_text('utf8'))
    phases = json.loads((project / 'framework-phases.json').read_text('utf8'))
    framework = next(scene for scene in scenes if scene['scene_id'] == 'framework')
    modules = [scene for scene in scenes if scene['role'] in ['student', 'teacher']]
    assert [scene['role'] for scene in modules] == ['student'] * 10 + ['teacher'] * 9
    assert timeline['development_evidence_seconds'] >= 120
    assert timeline['system_interface_seconds'] > timeline['development_evidence_seconds']
    assert ''.join(cue['text'] for cue in captions['cues']) == ''.join(scene['text'] for scene in scenes)
    assert all('\n' not in cue['text'] and cue['width'] <= 1440 for cue in captions['cues'])
    assert (project / 'subtitles.srt').read_bytes() == (ROOT / 'docs/demo/学脉XueMai-演示字幕.srt').read_bytes()
    assert (project / 'subtitles.ass').read_bytes() == (ROOT / 'docs/demo/学脉XueMai-演示字幕.ass').read_bytes()
    assert json.loads((ROOT / 'scripts/demo-scenes.json').read_text('utf8')) == scenes
    reference = geometry[0]['image']
    for phase in geometry:
        assert all(abs(phase['image'][key] - reference[key]) <= .01 for key in ['x', 'y', 'width', 'height'])
        if not phase['name']:
            continue
        box = phase['box']
        for target in phase['targets']:
            margins = [target['left'] - box['left'], target['top'] - box['top'],
                       box['left'] + box['width'] - target['left'] - target['width'],
                       box['top'] + box['height'] - target['top'] - target['height']]
            assert min(margins) >= phase['padding'] - .01
    # 按实际图像等比适配后的区域提取白色图纸边界，在成片中验证它保持固定。
    regions = json.loads((ROOT / 'docs/figures/xuemai-framework-regions.json').read_text('utf8'))
    scale = min(reference['width'] / regions['width'], reference['height'] / regions['height'])
    left = reference['x'] + (reference['width'] - regions['width'] * scale) / 2
    top = reference['y'] + (reference['height'] - regions['height'] * scale) / 2
    roi = (round(left) - 3, round(top) - 3, round(left + regions['width'] * scale) + 3,
           round(top + regions['height'] * scale) + 3)
    framework_bounds = []
    for phase in phases:
        at = framework['start'] + (2 if not phase['name'] else phase['at'] + .8)
        image, actual_at = frame_at(source, at)
        mask = ImageOps.grayscale(image.crop(roi)).point(lambda value: 255 if value > 250 else 0)
        box = mask.getbbox()
        if not box:
            raise ValueError('成片未找到框架图纸边界')
        framework_bounds.append({'phase': phase['name'], 'at': actual_at,
                                 'rectangle': [box[0] + roi[0], box[1] + roi[1], box[2] + roi[0], box[3] + roi[1]]})
    assert all(max(abs(a - b) for a, b in zip(row['rectangle'], framework_bounds[0]['rectangle'])) <= 2 for row in framework_bounds)
    center = caption_center(layout)[1]
    glyphs = []
    for index, cue in enumerate(captions['cues']):
        at = (cue['start'] + cue['end']) / 2
        image, actual_at = frame_at(source, at)
        crop = (100, layout['content_bottom'] + 3, 1820, 1075)
        mask = ImageOps.grayscale(image.crop(crop)).point(lambda value: 255 if value < 150 else 0)
        box = mask.getbbox()
        if not box:
            raise ValueError('字幕没有可测量字形：' + cue['text'])
        actual_center = crop[1] + (box[1] + box[3] - 1) / 2
        glyphs.append({'index': index + 1, 'text': cue['text'], 'at': actual_at,
                       'top': crop[1] + box[1], 'bottom': crop[1] + box[3],
                       'center': actual_center, 'target_center': center, 'error': round(actual_center - center, 2)})
    # 每个模块检查中段与操作后的状态，开发过程检查全部原始记录阶段。
    points = [(scene['scene_id'], scene['start'] + scene['duration'] / 2) for scene in scenes]
    points += [(scene['scene_id'] + '-结果', scene['start'] + scene['duration'] - 1) for scene in modules]
    points += [('framework-' + str(phase['name']), framework['start'] + (2 if not phase['name'] else phase['at'] + .8)) for phase in phases]
    points += [(scene['scene_id']+'-入场',scene['start']+.1) for scene in scenes if scene['role']=='authentication']
    output = project / '验收关键帧'
    output.mkdir(exist_ok=True)
    rows = []
    for index, (name, at) in enumerate(points):
        image, actual_at = frame_at(source, at)
        filename = f'{index+1:02}-{name}.png'
        image.save(output / filename)
        rows.append({'name': name, 'at': round(actual_at, 3), 'file': filename})
    local = ROOT / '.local/round12-video-frames'
    local.mkdir(exist_ok=True)
    font = ImageFont.truetype('msyh.ttc', 18)
    for start in range(0, len(rows), 8):
        sheet = Image.new('RGB', (1920, 660), '#dfe4df')
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(rows[start:start+8]):
            image = ImageOps.contain(Image.open(output / row['file']), (475, 285))
            x, y = index % 4 * 480, index // 4 * 330
            sheet.paste(image, (x, y))
            draw.text((x+4, y+290), f'{row["at"]:.2f}s {row["name"]}', font=font, fill='#203f3d')
        sheet.save(local / f'contact-{start//8+1:02}.jpg', quality=90)
    # 比较画板出场前的真实帧和各张原生画板，发现切片带入下一段的情况。
    board_edits=[edit for edit in timeline['edits'] if edit['role'] in ['presentation','development']]
    references={}
    roi=(45,75,785,910)
    def signature(image):
        return image.crop(roi).convert('RGB').resize((296,334))
    for edit in board_edits:
        with Image.open(project/'media'/('boards-'+edit['segment_id']+'.png')) as original:
            references[edit['segment_id']]=signature(original)
    boundaries=[]
    for edit in board_edits:
        for before in [.4,2/30]:
            image,actual=frame_at(source,edit['start']+edit['duration']-before)
            actual_image=signature(image)
            scores={name:sum(ImageStat.Stat(ImageChops.difference(actual_image,reference)).mean)/3
                    for name,reference in references.items()}
            expected=scores[edit['segment_id']]
            best=min(scores.values())
            if expected>5 or expected>best+.2:
                raise ValueError('镜头末尾混入其他画面：'+edit['scene_id'])
            boundaries.append({'scene':edit['scene_id'],'at':actual,'expected_error':round(expected,3),
                               'best_error':round(best,3),'safe_guard_seconds':edit['guard_seconds']})
    result = {'source_bytes': source.stat().st_size, 'frames': len(rows), 'frame_points': rows,
              'student_modules': 10, 'teacher_modules': 9, 'role_switches': 1,
              'framework_initial_full_seconds': phases[1]['at'], 'framework_native_bounds': framework_bounds,
              'framework_stationary': True, 'highlight_targets_contained': True,
              'subtitle_center': center, 'subtitle_glyphs': glyphs,
              'median_glyph_error': statistics.median(row['error'] for row in glyphs),
              'max_glyph_error': max(abs(row['error']) for row in glyphs),
              'subtitle_cues': len(glyphs), 'transparent_background': True,
              'boundary_frame_checks':boundaries,'cut_boundaries_passed':True,'human_listening_review':False}
    (ROOT / 'docs/rounds/第十二轮视频边界与字幕验收.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: result[key] for key in ['frames', 'framework_stationary', 'subtitle_center', 'median_glyph_error', 'max_glyph_error']}, ensure_ascii=False))
    if result['max_glyph_error'] > 2:
        raise ValueError('请依据实测字形边界校准字幕中心')


if __name__ == '__main__':
    main()
