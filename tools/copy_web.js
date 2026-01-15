const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STATIC = path.join(ROOT, 'static');
const OUT = path.join(ROOT, 'www');

function copyRecursive(src, dest){
  if(!fs.existsSync(src)) return;
  const stat = fs.statSync(src);
  if(stat.isDirectory()){
    if(!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });
    for(const name of fs.readdirSync(src)){
      copyRecursive(path.join(src, name), path.join(dest, name));
    }
  } else {
    fs.copyFileSync(src, dest);
  }
}

// Clean www
if(fs.existsSync(OUT)){
  fs.rmSync(OUT, { recursive: true, force: true });
}
fs.mkdirSync(OUT, { recursive: true });

// Copy UI root (ui.html -> index.html)
const uiSrc = path.join(ROOT, 'static', 'ui.html');
if(fs.existsSync(uiSrc)){
  copyRecursive(path.join(STATIC), OUT);
  // Make ui.html accessible as index.html
  const idx = path.join(OUT, 'index.html');
  if(!fs.existsSync(idx)){
    fs.copyFileSync(uiSrc, idx);
  }
} else {
  // fallback: copy whole repo static
  copyRecursive(STATIC, OUT);
}

// Copy audio and uploads folders so app can access them if needed
const audioSrc = path.join(ROOT, 'audio');
const uploadsSrc = path.join(ROOT, 'uploads');
if(fs.existsSync(audioSrc)) copyRecursive(audioSrc, path.join(OUT, 'audio'));
if(fs.existsSync(uploadsSrc)) copyRecursive(uploadsSrc, path.join(OUT, 'uploads'));

console.log('Web assets copied to', OUT);
