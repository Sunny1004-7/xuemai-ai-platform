// 只读核对指定提交在GitHub实际页面的Markdown渲染。
import { chromium, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { root } from './continuous-recorder.mjs'

const revision = process.argv[2] || execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
if (!/^[a-f0-9]{40}$/.test(revision)) throw new Error('请提供完整提交哈希')
const url = `https://github.com/Sunny1004-7/xuemai-ai-platform/blob/${revision}/README.md`
const output = path.join(root, 'docs/rounds/第十一轮GitHub展示')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' })
const page = await context.newPage()
const results = []
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
  const article = page.locator('.markdown-body').last()
  await expect(article).toBeVisible({ timeout: 30000 })
  const image = article.locator('img[alt="学脉总体方法与教学协同框架"]')
  await expect.poll(() => image.evaluate(image => image.complete && image.naturalWidth > 0), { timeout: 30000 }).toBe(true)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await page.evaluate(() => document.fonts.ready)
    const result = await article.evaluate(article => {
      const image = article.querySelector('img[alt="学脉总体方法与教学协同框架"]')
      const paragraph = image.closest('p')
      const imageBox = image.getBoundingClientRect()
      const paragraphBox = paragraph.getBoundingClientRect()
      const ordinary = [...article.querySelectorAll('p')].filter(p => !p.querySelector('img') && !p.closest('li,td,blockquote'))
      return {
        image_loaded: image.complete && image.naturalWidth > 0,
        image_center_error: Math.abs((imageBox.left + imageBox.right) / 2 - (paragraphBox.left + paragraphBox.right) / 2),
        image_within_container: imageBox.left >= paragraphBox.left - 1 && imageBox.right <= paragraphBox.right + 1,
        centered_container: paragraph.getAttribute('align'),
        paragraph_count: ordinary.length,
        indented_paragraph_count: ordinary.filter(p => p.textContent.startsWith('\u3000\u3000')).length,
        code_blocks: article.querySelectorAll('pre').length,
        tables: article.querySelectorAll('table').length,
        removed_copy_absent: !article.textContent.includes('系统版本') && !article.textContent.includes('使用边界与赛事证据'),
      }
    })
    if (!result.image_loaded || result.image_center_error > 1 || !result.image_within_container ||
        result.paragraph_count !== result.indented_paragraph_count || !result.removed_copy_absent || !result.tables || !result.code_blocks) {
      throw new Error('GitHub渲染核对未通过 ' + JSON.stringify(result))
    }
    const filename = `github-readme-${width}.png`
    await page.screenshot({ path: path.join(output, filename), fullPage: true })
    results.push({ width, screenshot: filename, ...result })
  }
  await writeFile(path.join(output, 'github-rendered.html'), await article.innerHTML())
  await writeFile(path.join(output, '验收结果.json'), JSON.stringify({ url, revision, actual_github_page: true, results }, null, 2))
  console.log(JSON.stringify({ revision, results }))
} finally {
  await browser.close()
}
