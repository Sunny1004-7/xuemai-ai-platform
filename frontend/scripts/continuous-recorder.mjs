// Chromium标签页原生媒体流连续录制，保留真实动画与流式变化。
import { chromium, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile, appendFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
export const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const python = path.join(root, '.venv/Scripts/python.exe')

export async function createRecorder({ base, directory }) {
  await mkdir(directory, { recursive: true })
  const title = 'XueMai_R7_' + Date.now()
  const context = await chromium.launchPersistentContext(path.join(directory, 'browser-profile-' + Date.now()), {
    channel: process.platform === 'win32' ? 'chrome' : undefined, headless: false, viewport: null,
    args: ['--app=' + base, '--window-position=80,80', '--window-size=1936,1060', '--force-device-scale-factor=1',
      '--auto-select-tab-capture-source-by-title=' + title, '--disable-backgrounding-occluded-windows',
      '--disable-background-timer-throttling', '--disable-renderer-backgrounding'],
  })
  await context.addInitScript(title => {
    window.addEventListener('DOMContentLoaded', () => {
      document.title = title
      const pointer = document.createElement('div')
      pointer.innerHTML = '<svg width="24" height="28" viewBox="0 0 24 28"><path d="M2 2L2 23L8 18L12 27L16 25L12 16L21 16Z" fill="#254b46" stroke="white" stroke-width="1.6"/></svg>'
      Object.assign(pointer.style, { position: 'fixed', left: '0', top: '0', zIndex: '2147483647', pointerEvents: 'none', transform: 'translate(-50px,-50px)' })
      document.body.append(pointer)
      document.addEventListener('mousemove', event => { pointer.style.transform = `translate(${event.clientX}px,${event.clientY}px)` })
    })
  }, title)
  const page = context.pages()[0] || await context.newPage()
  page.setDefaultTimeout(30000)
  await page.goto(base)
  const session = await context.newCDPSession(page)
  const { windowId, bounds } = await session.send('Browser.getWindowForTarget')
  const initial = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }))
  await session.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal', left: 80, top: 80,
    width: bounds.width + 1920 - initial.width, height: bounds.height + 1000 - initial.height } })
  await expect.poll(() => page.evaluate(() => [innerWidth, innerHeight])).toEqual([1920, 1000])
  let metrics = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio, zoom: getComputedStyle(document.documentElement).zoom }))
  if (metrics.dpr !== 1 || metrics.zoom !== '1') throw new Error('录制必须使用100%缩放和1倍像素比')
  const nativeFile = path.join(directory, 'continuous.webm')
  await writeFile(nativeFile, '')
  await context.exposeBinding('saveNativeVideoChunk', async (_, encoded) => appendFile(nativeFile, Buffer.from(encoded, 'base64')))
  const controller = await context.newPage()
  await controller.goto(base)
  await controller.setContent('<title>录制控制</title><button id="start">开始原生标签页录制</button>')
  await controller.evaluate(() => {
    window.recordingReady = false
    document.querySelector('#start').onclick = async () => {
      try {
        const stream = await navigator.mediaDevices.getDisplayMedia({ audio: false, video: { frameRate: { ideal: 30, max: 30 }, width: { ideal: 1920 }, height: { ideal: 1000 } }, selfBrowserSurface: 'include' })
        window.captureSettings = stream.getVideoTracks()[0].getSettings()
        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8', videoBitsPerSecond: 8000000 })
        let pending = Promise.resolve()
        recorder.ondataavailable = event => {
          if (!event.data.size) return
          pending = pending.then(async () => {
            const bytes = new Uint8Array(await event.data.arrayBuffer())
            let binary = ''
            for (let start = 0; start < bytes.length; start += 32768) binary += String.fromCharCode(...bytes.subarray(start, start + 32768))
            await window.saveNativeVideoChunk(btoa(binary))
          })
        }
        window.stopNativeRecording = () => new Promise(resolve => {
          recorder.onstop = async () => { await pending; stream.getTracks().forEach(track => track.stop()); resolve() }
          recorder.stop()
        })
        recorder.start(1000)
        window.recordingReady = true
      } catch (error) { window.recordingError = error.message }
    }
  })
  let started, settings
  const events = []
  async function start() {
    await controller.locator('#start').click()
    await expect.poll(() => controller.evaluate(() => window.recordingReady || window.recordingError), { timeout: 30000 }).toBe(true)
    settings = await controller.evaluate(() => window.captureSettings)
    if (settings.width !== 1920 || settings.height !== 1000 || settings.displaySurface !== 'browser') throw new Error('采集源尺寸或类型不符合专用标签页要求')
    await page.bringToFront()
    // 共享提示条会占用窗口高度，记录采集时实际视口，完整保留应用外壳。
    metrics = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio, zoom: getComputedStyle(document.documentElement).zoom }))
    if (metrics.width !== 1920 || metrics.height < 900 || metrics.dpr !== 1 || metrics.zoom !== '1') throw new Error('采集时视口或100%缩放发生变化')
    started = performance.now()
    await pause(300)
  }
  async function mark(name, operation) {
    const at = (performance.now() - started) / 1000
    events.push({ name, at: Number(at.toFixed(3)) })
    console.log(JSON.stringify(events.at(-1)))
    if (operation) await operation()
  }
  async function click(locator) {
    const box = await locator.boundingBox()
    if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 14 })
    await pause(200)
    await locator.click()
  }
  async function stop() {
    await controller.evaluate(() => window.stopNativeRecording())
    await writeFile(path.join(directory, 'recording.json'), JSON.stringify({ capture: 'Chromium getDisplayMedia标签页媒体流 / MediaRecorder VP8', requested_fps: 30,
      track_settings: settings, native_file: 'continuous.webm', metrics, events, elapsed_seconds: (performance.now() - started) / 1000 }, null, 2))
    await context.close()
    const ffmpeg = execFileSync(python, ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }).trim()
    execFileSync(ffmpeg, ['-y', '-v', 'error', '-i', nativeFile, '-vf', 'pad=1920:1080:0:0:color=0xf1f0e8', '-r', '30',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path.join(directory, 'continuous.mp4')], { windowsHide: true })
  }
  return { context, page, start, mark, click, stop, events }
}
