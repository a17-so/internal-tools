#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import os from 'os';
import { Command } from 'commander';
import { parse } from 'csv-parse/sync';
import open from 'open';

const CONFIG_DIR = path.join(os.homedir(), '.config', 'uploader-v2');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

function readConfig() {
  if (!fs.existsSync(CONFIG_FILE)) {
    return { baseUrl: process.env.UPLOADER_BASE_URL || 'http://localhost:3000', apiKey: null };
  }

  try {
    return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
  } catch {
    return { baseUrl: process.env.UPLOADER_BASE_URL || 'http://localhost:3000', apiKey: null };
  }
}

function writeConfig(config) {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

function resolveBaseUrl(optionUrl) {
  return optionUrl || readConfig().baseUrl || process.env.UPLOADER_BASE_URL || 'http://localhost:3000';
}

function getApiKey(optionApiKey) {
  return optionApiKey || process.env.UPLOADER_API_KEY || readConfig().apiKey;
}

async function request(baseUrl, endpoint, options = {}) {
  const res = await fetch(`${baseUrl}${endpoint}`, options);
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }

  return data;
}

async function authedRequest(baseUrl, endpoint, apiKey, options = {}) {
  if (!apiKey) {
    throw new Error('No API key configured. Run `uploader auth token create` first.');
  }

  const headers = {
    ...(options.headers || {}),
    authorization: `Bearer ${apiKey}`,
  };

  return request(baseUrl, endpoint, { ...options, headers });
}

function normalizeCsvRow(row, root) {
  const fileType = (row.file_type || '').trim();
  const accountId = (row.account_id || '').trim();
  const mode = (row.mode || 'draft').trim();
  const caption = row.caption || '';
  const platform = (row.platform || 'tiktok').trim();

  if (!fileType || !accountId || !mode) {
    throw new Error('CSV row missing required fields: file_type, account_id, mode');
  }

  if (fileType === 'video') {
    const videoPathRaw = (row.video_path || '').trim();
    if (!videoPathRaw) throw new Error('video row missing video_path');
    const videoPath = path.isAbsolute(videoPathRaw) ? videoPathRaw : path.join(root, videoPathRaw);

    return {
      connectedAccountId: accountId,
      postType: 'video',
      mode,
      caption,
      provider: platform,
      videoPath,
      clientRef: row.client_ref || undefined,
    };
  }

  if (fileType === 'slideshow') {
    const imagePathsRaw = (row.image_paths || '').trim();
    if (!imagePathsRaw) throw new Error('slideshow row missing image_paths');

    const imagePaths = imagePathsRaw.split(';').map((p) => p.trim()).filter(Boolean).map((p) => (
      path.isAbsolute(p) ? p : path.join(root, p)
    ));

    return {
      connectedAccountId: accountId,
      postType: 'slideshow',
      mode,
      caption,
      provider: platform,
      imagePaths,
      clientRef: row.client_ref || undefined,
    };
  }

  throw new Error(`Unknown file_type: ${fileType}`);
}

const program = new Command();
program.name('uploader').description('Uploader V2 CLI').version('0.1.0');

program
  .command('auth:login')
  .description('Open browser login page')
  .option('--base-url <url>', 'Uploader base URL')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    await open(`${baseUrl}/login`);
    console.log(`Opened ${baseUrl}/login`);
  });

program
  .command('auth:token:create')
  .description('Create API key using app credentials')
  .requiredOption('--email <email>', 'Operator email')
  .requiredOption('--password <password>', 'Operator password')
  .option('--name <name>', 'Key name', 'CLI Key')
  .option('--base-url <url>', 'Uploader base URL')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);

    const loginRes = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: opts.email, password: opts.password }),
    });

    const loginData = await loginRes.json();
    if (!loginRes.ok) {
      throw new Error(loginData.error || 'Login failed');
    }

    const cookie = loginRes.headers.get('set-cookie');
    if (!cookie) {
      throw new Error('Session cookie not returned by server');
    }

    const keyRes = await fetch(`${baseUrl}/api/auth/api-keys`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        cookie,
      },
      body: JSON.stringify({ name: opts.name }),
    });

    const keyData = await keyRes.json();
    if (!keyRes.ok) {
      throw new Error(keyData.error || 'Failed to create API key');
    }

    const config = readConfig();
    config.baseUrl = baseUrl;
    config.apiKey = keyData.apiKey.token;
    writeConfig(config);

    console.log('API key created and saved to config.');
    console.log(`Key prefix: ${keyData.apiKey.keyPrefix}`);
  });

program
  .command('accounts:list')
  .description('List connected accounts')
  .option('--provider <provider>', 'Filter provider', 'tiktok')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, `/api/accounts?provider=${encodeURIComponent(opts.provider)}`, apiKey);
    for (const account of data.accounts || []) {
      console.log(`${account.id}\t${account.provider}\t${account.displayName || account.username || account.externalAccountId}`);
    }
  });

program
  .command('accounts:connect-instagram')
  .description('Connect Instagram account using access token + IG user ID')
  .requiredOption('--instagram-user-id <id>', 'Instagram professional account user ID')
  .requiredOption('--access-token <token>', 'Instagram Graph API access token')
  .option('--display-name <name>', 'Display name override')
  .option('--username <name>', 'Username override')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, '/api/accounts/instagram/connect', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instagramUserId: opts.instagramUserId,
        accessToken: opts.accessToken,
        displayName: opts.displayName,
        username: opts.username,
      }),
    });

    console.log(`Connected Instagram account ${data.account.id}`);
  });

program
  .command('accounts:connect-youtube')
  .description('Connect YouTube account using access token')
  .requiredOption('--access-token <token>', 'YouTube Data API access token')
  .option('--display-name <name>', 'Display name override')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, '/api/accounts/youtube/connect', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        accessToken: opts.accessToken,
        displayName: opts.displayName,
      }),
    });

    console.log(`Connected YouTube account ${data.account.id}`);
  });

program
  .command('accounts:connect-facebook')
  .description('Connect Facebook page using page token + page id')
  .requiredOption('--page-id <id>', 'Facebook page id')
  .requiredOption('--access-token <token>', 'Facebook page access token')
  .option('--display-name <name>', 'Display name override')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, '/api/accounts/facebook/connect', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pageId: opts.pageId,
        accessToken: opts.accessToken,
        displayName: opts.displayName,
      }),
    });

    console.log(`Connected Facebook account ${data.account.id}`);
  });

program
  .command('upload:file')
  .description('Queue a single video file')
  .requiredOption('--account <id>', 'Connected account id')
  .requiredOption('--caption <text>', 'Caption')
  .requiredOption('--file <path>', 'Video path')
  .option('--mode <mode>', 'draft|direct', 'draft')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .option('--send-now', 'Trigger dispatcher after enqueue', true)
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, '/api/uploads/jobs', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connectedAccountId: opts.account,
        mode: opts.mode,
        postType: 'video',
        caption: opts.caption,
        videoPath: path.resolve(opts.file),
        sendNow: Boolean(opts.sendNow),
      }),
    });

    console.log(`Queued job ${data.job.id}${data.duplicate ? ' (duplicate)' : ''}`);
  });

program
  .command('upload:slideshow')
  .description('Queue a slideshow post')
  .requiredOption('--account <id>', 'Connected account id')
  .requiredOption('--caption <text>', 'Caption')
  .requiredOption('--images <paths>', 'Comma-separated image paths')
  .option('--mode <mode>', 'draft|direct', 'draft')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .option('--send-now', 'Trigger dispatcher after enqueue', true)
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const images = String(opts.images)
      .split(',')
      .map((v) => path.resolve(v.trim()))
      .filter(Boolean);

    const data = await authedRequest(baseUrl, '/api/uploads/jobs', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connectedAccountId: opts.account,
        mode: opts.mode,
        postType: 'slideshow',
        caption: opts.caption,
        imagePaths: images,
        sendNow: Boolean(opts.sendNow),
      }),
    });

    console.log(`Queued job ${data.job.id}${data.duplicate ? ' (duplicate)' : ''}`);
  });

program
  .command('upload:batch')
  .description('Queue a batch using CSV schema')
  .requiredOption('--csv <path>', 'CSV file path')
  .option('--root <path>', 'Path root for relative media paths', '.')
  .option('--name <name>', 'Batch name', `CLI Batch ${new Date().toISOString()}`)
  .option('--send-now', 'Trigger dispatcher after enqueue', true)
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);
    const csvPath = path.resolve(opts.csv);
    const root = path.resolve(opts.root);

    const raw = fs.readFileSync(csvPath, 'utf8');
    const rows = parse(raw, { columns: true, skip_empty_lines: true, trim: true });
    const jobs = rows.map((row) => normalizeCsvRow(row, root));

    const data = await authedRequest(baseUrl, '/api/uploads/batches', apiKey, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: opts.name,
        jobs,
        sendNow: Boolean(opts.sendNow),
      }),
    });

    console.log(`Batch ${data.batch.id} created with ${data.jobs.length} jobs`);
  });

program
  .command('jobs:list')
  .description('List jobs')
  .option('--status <csv>', 'Status filter (comma-separated)', 'queued,running,failed')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const data = await authedRequest(baseUrl, `/api/uploads/jobs?status=${encodeURIComponent(opts.status)}`, apiKey);
    for (const job of data.jobs || []) {
      console.log(`${job.id}\t${job.status}\t${job.postType}\t${job.mode}\t${job.createdAt}`);
    }
  });

program
  .command('jobs:retry')
  .description('Retry failed jobs by batch id')
  .requiredOption('--batch <id>', 'Batch id')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const list = await authedRequest(baseUrl, `/api/uploads/jobs?batchId=${encodeURIComponent(opts.batch)}&status=failed,canceled`, apiKey);
    for (const job of list.jobs || []) {
      await authedRequest(baseUrl, `/api/uploads/jobs/${job.id}/retry`, apiKey, { method: 'POST' });
      console.log(`Retried ${job.id}`);
    }
  });

program
  .command('jobs:cancel')
  .description('Cancel queued/running jobs by batch id')
  .requiredOption('--batch <id>', 'Batch id')
  .option('--base-url <url>', 'Uploader base URL')
  .option('--api-key <key>', 'API key override')
  .action(async (opts) => {
    const baseUrl = resolveBaseUrl(opts.baseUrl);
    const apiKey = getApiKey(opts.apiKey);

    const list = await authedRequest(baseUrl, `/api/uploads/jobs?batchId=${encodeURIComponent(opts.batch)}&status=queued,running`, apiKey);
    for (const job of list.jobs || []) {
      await authedRequest(baseUrl, `/api/uploads/jobs/${job.id}/cancel`, apiKey, { method: 'POST' });
      console.log(`Canceled ${job.id}`);
    }
  });

program.parseAsync(process.argv).catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
