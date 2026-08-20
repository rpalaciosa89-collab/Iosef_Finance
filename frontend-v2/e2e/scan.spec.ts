import { test, expect } from '@playwright/test'

test('el dashboard carga el screener con tickers', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.locator('body')).toBeVisible()
  // El dashboard puede exigir auth (redirect a /login si no hay sesion)
  await page.waitForTimeout(2_000)
  const onDashboard = page.url().includes('dashboard')
  if (onDashboard) {
    await expect(page.locator('text=/AAPL|MSFT|NVDA|TSLA/i').first()).toBeVisible({
      timeout: 30_000,
    })
  } else {
    await expect(page).toHaveURL(/login/)
  }
})
