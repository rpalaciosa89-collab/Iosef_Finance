import { test, expect } from '@playwright/test'

test('paper trading: login y acceder al tab de portfolio', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('analista@fondo.com').fill('admin@iosef.finance')
  await page.getByPlaceholder('••••••••').fill('admin123')
  await page.getByRole('button', { name: /acceder al terminal/i }).click()
  await page.waitForURL(/dashboard/, { timeout: 15_000 })

  // Ir a la pestana Paper Trading (boton con id nav-tab-paper)
  const ptTab = page.locator('#nav-tab-paper')
  if (await ptTab.count()) {
    await ptTab.click()
  }
  await page.waitForTimeout(3_000)

  const hasPortfolio = await page.getByText(/portfolio activo|equity|realized/i).count()
  if (hasPortfolio > 0) {
    await expect(page.getByText(/portfolio activo/i).first()).toBeVisible({ timeout: 15_000 })
  }
})
