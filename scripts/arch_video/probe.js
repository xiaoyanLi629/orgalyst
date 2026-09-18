const puppeteer=require(process.env.PUP);const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await puppeteer.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true,args:["--no-sandbox","--window-size=1920,1080"]});
const p=await b.newPage();await p.setViewport({width:1920,height:1080,deviceScaleFactor:1});
await p.emulateMediaFeatures([{name:'prefers-color-scheme',value:'light'},{name:'prefers-reduced-motion',value:'no-preference'}]);
await p.goto('file://'+process.env.S+'/arch_video/orgalyst.architecture.html',{waitUntil:'load'});await sleep(1500);
const info=await p.evaluate(()=>{const q=s=>document.querySelector(s);const m=q('#btn-motion');const svg=q('svg[data-motion], [data-motion]');
return {motionHidden:m.hidden,motionPressed:m.getAttribute('aria-pressed'),dataMotion:svg&&svg.getAttribute('data-motion'),
chapters:[...document.querySelectorAll('#guided-view-chapters button')].map(b=>b.textContent.trim()),
playDisabled:q('#guided-view-play').disabled, trail:document.querySelectorAll('#guided-view-trail [data-story-node]').length,
scrollW:document.documentElement.scrollWidth, scrollH:document.documentElement.scrollHeight,
nodes:[...document.querySelectorAll('[data-node-id]')].slice(0,3).map(n=>n.getAttribute('data-node-id')),
present:q('#present-label').textContent.trim(), theme:q('#btn-theme').getAttribute('aria-label')};});
console.log(JSON.stringify(info,null,1));
await p.screenshot({path:'probe0.png'});
await p.click('#guided-view-chapters button');await sleep(800);
const t2=await p.evaluate(()=>({trail:[...document.querySelectorAll('#guided-view-trail [data-story-node]')].map(b=>b.getAttribute('data-story-node')),note:document.querySelector('#guided-view-note').textContent.trim().slice(0,80)}));
console.log(JSON.stringify(t2));
await p.screenshot({path:'probe1.png'});
const stops=await p.$$('#guided-view-trail [data-story-node]');if(stops[2]){await stops[2].click();await sleep(800);await p.screenshot({path:'probe2.png'});}
await b.close();})();
