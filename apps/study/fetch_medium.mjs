#!/usr/bin/env node
/**
 * Fetch a Medium article using Puppeteer with a persistent Chrome profile.
 * Cookies from a previous login session persist, so Medium membership content
 * is accessible without re-authenticating each time.
 *
 * Usage:
 *   node fetch_medium.mjs <article_url>        # headless fetch
 *   node fetch_medium.mjs --setup               # open browser for one-time Medium login
 *
 * Output (stdout): JSON { title, author, text, cover, url }
 */

import puppeteer from 'puppeteer-core';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROFILE_DIR = path.resolve(__dirname, '..', 'chrome-profile');

// Find Chrome executable
function findChrome() {
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const c of candidates) {
    try {
      execSync(`test -f "${c}"`, { stdio: 'ignore' });
      return c;
    } catch {}
  }
  return 'google-chrome';
}

async function setup() {
  console.error('Opening Chrome for Medium login...');
  console.error('Log in to Medium, then close the browser window.');
  const browser = await puppeteer.launch({
    headless: false,
    executablePath: findChrome(),
    userDataDir: PROFILE_DIR,
    args: ['--no-first-run', '--disable-default-apps'],
  });
  const page = await browser.newPage();
  await page.goto('https://medium.com/m/signin', { waitUntil: 'networkidle2' });
  // Wait for user to log in and close the browser
  await new Promise(resolve => browser.on('disconnected', resolve));
  console.error('Browser closed. Cookies saved to chrome-profile/');
}

async function fetchArticle(url) {
  const browser = await puppeteer.launch({
    headless: false,
    executablePath: findChrome(),
    userDataDir: PROFILE_DIR,
    args: [
      '--no-first-run',
      '--disable-default-apps',
      '--disable-extensions',
      '--window-position=-2400,-2400',
      '--window-size=1280,900',
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });

    // Wait for Cloudflare challenge to resolve (if present)
    const hasChallenge = await page.evaluate(() =>
      document.body.innerText.includes('security verification') ||
      document.body.innerText.includes('Just a moment')
    );
    if (hasChallenge) {
      console.error('  Cloudflare challenge detected, waiting up to 15s...');
      await page.waitForFunction(
        () => !document.body.innerText.includes('security verification') &&
              !document.body.innerText.includes('Just a moment'),
        { timeout: 15000 }
      ).catch(() => {});
    }

    // Wait for article content to render
    await page.waitForSelector('article', { timeout: 10000 }).catch(() => {});

    const data = await page.evaluate(() => {
      const article = document.querySelector('article');
      const text = article ? article.innerText : document.body.innerText;

      // Title
      const h1 = document.querySelector('h1');
      const ogTitle = document.querySelector('meta[property="og:title"]');
      const title = h1?.innerText || ogTitle?.content || document.title || '';

      // Author
      const authorMeta = document.querySelector('meta[name="author"]');
      const authorLink = document.querySelector('a[rel="author"]');
      const author = authorMeta?.content || authorLink?.innerText || '';

      // Cover image
      const ogImage = document.querySelector('meta[property="og:image"]');
      const cover = ogImage?.content || '';

      return { title, author, text, cover };
    });

    data.url = url;
    process.stdout.write(JSON.stringify(data));
  } finally {
    await browser.close();
  }
}

// ── Main ────────────────────────────────────────────────────────────────────

const arg = process.argv[2];

if (!arg) {
  console.error('Usage: node fetch_medium.mjs <url> | --setup');
  process.exit(2);
}

if (arg === '--setup') {
  setup().catch(e => { console.error(e); process.exit(1); });
} else {
  fetchArticle(arg).catch(e => {
    console.error('Fetch failed:', e.message);
    // Output empty result so Python can fall back
    process.stdout.write(JSON.stringify({ title: '', author: '', text: '', cover: '', url: arg, error: e.message }));
    process.exit(1);
  });
}
