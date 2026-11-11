import {test,expect} from '@playwright/test'

test('课程切换更新学习首项且作答反馈显示状态变化与后续路径',async ({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:'进入学脉',exact:true}).click()
  await expect(page.locator('.next-study')).toBeVisible()
  await page.getByLabel('切换当前课程').selectOption('2')
  await expect(page.locator('.study-meta')).toContainText('Python')
  await expect(page.locator('.next-study > .button')).toHaveAttribute('href',/course=2/)
  await page.getByLabel('切换当前课程').selectOption('1')
  await page.goto('/practice?question=1')
  await page.getByRole('radio').nth(2).check()
  await page.getByRole('button',{name:'提交答案',exact:true}).click()
  await expect(page.locator('.knowledge-change')).toContainText('知识状态')
  await expect(page.locator('.feedback-path a')).toHaveCount(2)
})

test('教师四个学情工作区保持筛选并可分别完成任务',async ({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:'教师端',exact:true}).click()
  await page.getByRole('button',{name:'进入学脉',exact:true}).click()
  await expect(page.locator('.teacher-desk')).toBeVisible()
  await page.goto('/analytics')
  await page.getByLabel('筛选学情章节').selectOption('1')
  for (const [tab,region] of [['教学干预','view-intervention'],['学生轨迹','view-students'],['作答复核','view-review'],['知识矩阵','view-matrix']]) {
    await page.getByRole('tab',{name:new RegExp(tab)}).click()
    await expect(page.locator(`#${region}`)).toBeVisible()
    await expect(page.getByRole('tabpanel')).toHaveCount(1)
  }
  await expect(page.getByLabel('筛选学情章节')).toHaveValue('1')
})
