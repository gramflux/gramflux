const {test, expect} = require('@playwright/test');

function runtimeErrors(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}

test('homepage navigates to a usable English quick start', async ({page}) => {
  const errors = runtimeErrors(page);
  await page.goto('./');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', {level: 1})).toHaveText('One client.Every layer.');
  await page.getByRole('link', {name: 'Get started'}).click();
  await expect(page.getByRole('heading', {level: 1})).toHaveText('Your first client');
  await expect(page.locator('article')).toContainText('Session.create');
  await expect(page.locator('article')).toContainText('require_authorized=False');
  expect(errors).toEqual([]);
});

test('generated raw reference exposes method parameters and stable anchors', async ({page}) => {
  const response = await page.goto('docs/reference/raw/messages/#get_history');
  expect(response.status()).toBe(200);
  await expect(page.locator('#get_history')).toBeVisible();
  await expect(page.locator('article')).toContainText('client.api.messages.get_history');
  await expect(page.locator('article')).toContainText('offset_date');
  await expect(page.locator('article')).toContainText('0x4423e6c5');
  await page.goto('docs/reference/events/');
  const clientField = page.locator('article table').first().getByRole('row').filter({hasText: 'client'});
  await expect(clientField.getByRole('cell').nth(1)).toHaveText('Client | None');
});

test('local search returns resumable login documentation without a service key', async ({page}) => {
  const external = [];
  page.on('request', request => {
    if (new URL(request.url()).hostname !== '127.0.0.1') external.push(request.url());
  });
  await page.goto('./');
  await page.getByRole('button', {name: 'Search Search...', exact: true}).click();
  const search = page.locator('input.aa-Input:visible');
  await search.fill('resumable');
  await expect(page.locator('.aa-Item').first()).toBeVisible();
  await expect(page.locator('.aa-Panel')).toContainText(/login|authentication/i);
  await page.locator('.aa-Item').first().click();
  await expect(page).toHaveURL(/docs\//);
  expect(external).toEqual([]);
});

test('theme preference persists after navigation', async ({page}) => {
  await page.goto('./');
  const toggle = page.getByRole('button', {name: /switch between dark and light mode/i});
  for (let attempt = 0; attempt < 3 && await page.locator('html').getAttribute('data-theme') !== 'dark'; attempt++) {
    await toggle.click();
  }
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('link', {name: 'Get started'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('code copy uses the real code block and clipboard', async ({page, context}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('docs/getting-started/quickstart/');
  const block = page.locator('div[class*="codeBlockContainer"]').filter({hasText: 'async def main'}).first();
  await block.hover();
  await block.getByRole('button', {name: /copy/i}).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Session.create("account")');
});

test('mobile navigation opens without page overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('./');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', {name: /toggle navigation bar/i}).click();
  await page.getByRole('link', {name: 'Documentation', exact: true}).click();
  await expect(page.locator('article')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('individual Client reference explains defaults, entities and return behavior', async ({page}) => {
  const errors = runtimeErrors(page);
  await page.goto('docs/reference/client/send_message/');
  await expect(page.getByRole('heading', {level: 1})).toHaveText('Client.send_message');
  for (const parameter of ['peer', 'text', 'reply_to', 'silent', 'link_preview', 'reply_markup', 'entities']) {
    await expect(page.locator(`article h3#${parameter}`)).toBeVisible();
  }
  await expect(page.locator('article')).toContainText('UTF-16');
  await expect(page.locator('article')).toContainText('Keyword-only');
  await expect(page.locator('article')).toContainText('None');
  expect(errors).toEqual([]);
});

test('individual raw reference distinguishes native inputs and ordinary flags', async ({page}) => {
  const errors = runtimeErrors(page);
  await page.goto('docs/reference/raw/messages/get_history/');
  await expect(page.locator('article')).toContainText('InputPeerSelf');
  await expect(page.locator('article')).toContainText('access_hash');
  await expect(page.locator('article h3#offset_date')).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto('docs/reference/raw/auth/import_bot_authorization/');
  await expect(page.locator('article h3#flags')).toBeVisible();
  const flags = page.locator('article table').first().getByRole('row').filter({hasText: 'flags'});
  await expect(flags).toContainText('Required');
  expect(errors).toEqual([]);
});
