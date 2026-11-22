import { startEditorServer } from './service.js';

const host = '127.0.0.1';
const port = Number(process.env.PORT || 55173);

startEditorServer({ host, port })
  .then(({ url }) => {
    console.log(`[dsh-np-ppt] editor server listening at ${url}`);
  })
  .catch((err) => {
    console.error('[dsh-np-ppt] failed to start editor server:', err);
    process.exit(1);
  });
