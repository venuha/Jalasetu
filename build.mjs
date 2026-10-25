import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
await build({absWorkingDir:fileURLToPath(new URL('.',import.meta.url)),entryPoints:['frontend/main.jsx'],bundle:true,minify:true,outfile:'app/static/app.js',define:{'process.env.NODE_ENV':'"production"'}});
console.log('React production bundle built.');
