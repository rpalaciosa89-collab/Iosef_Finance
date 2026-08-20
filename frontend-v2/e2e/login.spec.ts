import { test, expect } from '@playwright/test'

test('login con credenciales validas redirige al dashboard', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('analista@fondo.com').fill('admin@iosef.finance')
  await page.getByPlaceholder('••••••••').fill('admin123')
  await page.getByRole('button', { name: /acceder al terminal/i }).click()
  await page.waitForURL(/dashboard/, { timeout: 15_000 })
  await expect(page).toHaveURL(/dashboard/)
})

test('login con clave incorrecta muestra error', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('analista@fondo.com').fill('admin@iosef.finance')
  await page.getByPlaceholder('••••••••').fill('wrong-pass')
  await page.getByRole('button', { name: /acceder al terminal/i }).click()
  await expect(page.locator('text=/incorrect|invalid|error|401/i')).toBeVisible({ timeout: 10_000 })
})
