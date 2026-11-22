import { createReadStream, statSync, mkdirSync, writeFileSync, existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, execFile, execSync } from 'node:child_process';
import { tmpdir } from 'node:os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
export const packageRoot = resolve(__dirname, '..');
export const defaultEditorDirectory = resolve(packageRoot, 'editor');
export const compilerScriptPath = resolve(packageRoot, 'compiler', 'export_pptx.py');

const contentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
  ['.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'],
]);

function respond(response, statusCode, message) {
  response.writeHead(statusCode, {
    'Content-Type': 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  response.end(message);
}

function readBody(request) {
  return new Promise((resolveBody, rejectBody) => {
    const chunks = [];
    request.on('data', (chunk) => chunks.push(chunk));
    request.on('error', rejectBody);
    request.on('end', () => resolveBody(Buffer.concat(chunks)));
  });
}

export function packageVenvPython() {
  const venvPython = resolve(packageRoot, '.venv', 'bin', 'python');
  if (!existsSync(venvPython)) return null;
  try {
    execFileSync(`${venvPython} -c "import pptx,yaml"`, { shell: true, timeout: 5000, encoding: 'utf-8', stdio: ['ignore', 'ignore', 'ignore'] });
    return venvPython;
  } catch { return null; }
}

export function findPython() {
  // Prefer the plugin-local venv (deps pre-installed there), then system python
  const venv = packageVenvPython();
  if (venv) return venv;
  const candidates = ['py -3', 'python3', 'python'];
  for (const cmd of candidates) {
    try {
      const version = execFileSync(cmd + ' --version', { shell: true, timeout: 5000, encoding: 'utf-8' });
      if (version.includes('Python')) {
        // Only accept system python if python-pptx is actually importable; otherwise the export engine tries a `--user` install that often fails.
        try {
          execFileSync(cmd + ' -c "import pptx,yaml"', { shell: true, timeout: 5000, encoding: 'utf-8', stdio: ['ignore', 'ignore', 'ignore'] });
          return cmd;
        } catch { /* keep scanning for a python that already has the deps */ }
      }
    } catch {}
  }
  // Fallback: last system python found above (best-effort); it will trigger the venv bootstrap inside export_pptx.py.
  for (const cmd of candidates) {
    try {
      const version = execFileSync(cmd + ' --version', { shell: true, timeout: 5000, encoding: 'utf-8' });
      if (version.includes('Python')) return cmd;
    } catch {}
  }
  return null;
}

export function handleExport(request, response) {
  readBody(request)
    .then((body) => {
      let payload;
      try {
        payload = JSON.parse(body.toString('utf-8'));
      } catch {
        respond(response, 400, 'Invalid JSON body');
        return;
      }

      const manifestContent = payload.manifestContent || '';
      const pages = Array.isArray(payload.pages) ? payload.pages : [];
      const deckTitle = (payload.title || 'deck').replace(/[<>:"/\\|?*]/g, '_');

      const tmpDir = mkdtempSync(resolve(tmpdir(), 'pptd-export-'));
      const manifestPath = resolve(tmpDir, 'deck.pptd');
      const pagesDir = resolve(tmpDir, 'pages');
      mkdirSync(pagesDir, { recursive: true });
      writeFileSync(manifestPath, manifestContent, 'utf-8');

      for (const page of pages) {
        const pagePath = resolve(tmpDir, page.path || 'pages/page.page');
        mkdirSync(dirname(pagePath), { recursive: true });
        writeFileSync(pagePath, page.content || '', 'utf-8');
      }

      const scriptPath = existsSync(compilerScriptPath) ? compilerScriptPath : resolve(packageRoot, 'scripts', 'export_pptx.py');
      if (!existsSync(scriptPath)) {
        respond(response, 500, 'export_pptx.py compiler not found');
        return;
      }

      const outPptx = resolve(tmpDir, `${deckTitle}.pptx`);
      const pythonCmd = findPython();
      if (!pythonCmd) {
        respond(response, 500, 'Python not found. Please install Python 3.');
        return;
      }

      const fullCmd = `${pythonCmd} "${scriptPath}" "${manifestPath}" --output "${outPptx}" --force`;

      try {
        execFileSync(fullCmd, {
          cwd: tmpDir,
          shell: true,
          timeout: 30000,
          encoding: 'utf-8',
          stdio: ['ignore', 'pipe', 'pipe'],
        });

        if (existsSync(outPptx)) {
          const stats = statSync(outPptx);
          const fileData = readFileSync(outPptx);
          response.writeHead(200, {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'Content-Disposition': `attachment; filename="${encodeURIComponent(deckTitle)}.pptx"`,
            'Content-Length': stats.size,
            'Cache-Control': 'no-store',
          });
          response.end(fileData);
        } else {
          respond(response, 500, 'Export completed but output file not found');
        }
      } catch (err) {
        const errMsg = (err.stderr || '') + (err.message || '') + String(err);
        respond(response, 500, `Export failed: ${errMsg.slice(-500)}`);
      }
    })
    .catch((err) => respond(response, 500, `Body read error: ${err.message}`));
}

export function createEditorServer({ editorDirectory = defaultEditorDirectory } = {}) {
  const root = resolve(editorDirectory);
  const rootPrefix = `${root}${sep}`;

  return createServer((request, response) => {
    if (request.method === 'POST') {
      let pathname;
      try {
        pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
      } catch {
        respond(response, 400, 'Bad Request');
        return;
      }
      if (pathname === '/api/export') {
        handleExport(request, response);
        return;
      }
      respond(response, 404, 'Not Found');
      return;
    }

    if (request.method !== 'GET' && request.method !== 'HEAD') {
      respond(response, 405, 'Method Not Allowed');
      return;
    }

    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
    } catch {
      respond(response, 400, 'Bad Request');
      return;
    }

    // 代理 /neo-ppt/ 页面以实现同源拦截
    if (pathname === '/neo-ppt' || pathname === '/neo-ppt/' || pathname.startsWith('/neo-ppt/')) {
      const targetUrl = new URL(request.url ?? '/neo-ppt/', 'https://www.kimi.com').toString();
      fetch(targetUrl, {
        headers: {
          'User-Agent': request.headers['user-agent'] || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
          'Accept-Language': request.headers['accept-language'] || 'zh-CN,zh;q=0.9',
        },
      })
        .then(async (res) => {
          let html = await res.text();
          html = html.replace(/src="\/\/statics\./g, 'src="https://statics.');
          html = html.replace(/href="\/\/statics\./g, 'href="https://statics.');
          html = html.replace(/src=\x27\/\/statics\./g, "src='https://statics.");
          html = html.replace(/href=\x27\/\/statics\./g, "href='https://statics.");

          const injectScript = `<script>
(function() {
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('.form-submit button, button.storage-picker, .download-content .form-submit button');
    if (!btn) return;

    const radioItems = document.querySelectorAll('.radio-group-item');
    let isPpt = true;
    for (const r of radioItems) {
      if (r.classList.contains('active')) {
        const text = (r.textContent || '').trim();
        if (text.includes('图片') || text.includes('Image')) {
          isPpt = false;
        }
        break;
      }
    }

    if (isPpt) {
      if (window.parent && window.parent.neoDeck && typeof window.parent.neoDeck.exportPptx === 'function') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        window.parent.neoDeck.exportPptx();

        setTimeout(function() {
          const closeBtn = document.querySelector('.icon-button[aria-label="关闭"], .close-icon, button.message-close');
          if (closeBtn) {
            closeBtn.click();
          } else {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, bubbles: true }));
          }
        }, 150);
      }
    }
  }, true);
})();
</script>`;
          html = html.replace('</head>', injectScript + '</head>');
          const bodyBuf = Buffer.from(html, 'utf-8');
          response.writeHead(200, {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': bodyBuf.length,
            'Cache-Control': 'no-store',
          });
          response.end(bodyBuf);
        })
        .catch((err) => {
          respond(response, 502, 'Proxy error: ' + err.message);
        });
      return;
    }

    if (pathname.endsWith('/')) pathname += 'index.html';
    const filePath = resolve(root, `.${pathname}`);
    if (filePath !== root && !filePath.startsWith(rootPrefix)) {
      respond(response, 403, 'Forbidden');
      return;
    }

    let stats;
    try {
      stats = statSync(filePath);
    } catch {
      respond(response, 404, 'Not Found');
      return;
    }

    if (!stats.isFile()) {
      respond(response, 404, 'Not Found');
      return;
    }

    response.writeHead(200, {
      'Content-Type': contentTypes.get(extname(filePath).toLowerCase()) ?? 'application/octet-stream',
      'Content-Length': stats.size,
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    });

    if (request.method === 'HEAD') {
      response.end();
      return;
    }

    const stream = createReadStream(filePath);
    stream.on('error', () => response.destroy());
    stream.pipe(response);
  });
}

export function startEditorServer({ host = '127.0.0.1', port = 55173 } = {}) {
  const server = createEditorServer();

  return new Promise((resolvePromise, reject) => {
    const onError = (error) => reject(error);
    server.once('error', onError);
    server.listen(port, host, () => {
      server.off('error', onError);
      const address = server.address();
      const actualPort = typeof address === 'object' && address ? address.port : port;
      resolvePromise({ server, url: `http://${host}:${actualPort}/` });
    });
  });
}

export function runExportPptx(manifestPath, outputPath, transition = 'fade', force = true) {
  return new Promise((resolveExport, rejectExport) => {
    const pythonCmd = findPython();
    if (!pythonCmd) {
      return rejectExport(new Error('Python 3 not found on system.'));
    }
    const outArg = outputPath ? `--output "${outputPath}"` : '';
    const transArg = `--transition ${transition}`;
    const forceArg = force ? '--force' : '';
    const cmd = `${pythonCmd} "${compilerScriptPath}" "${manifestPath}" ${outArg} ${transArg} ${forceArg}`;

    execFile(cmd, { shell: true }, (err, stdout, stderr) => {
      if (err) {
        return rejectExport(new Error((stderr || '') + (err.message || '')));
      }
      resolveExport({ output: stdout + (stderr || ''), exitCode: 0 });
    });
  });
}
