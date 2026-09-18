const puppeteer=require(process.env.PUP);const fs=require('fs');const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const LANG=process.env.LANG_;const script=JSON.parse(fs.readFileSync('script.json'));const durKey=LANG==='zh'?'dur':'dur_en';const outDir=LANG==='zh'?'seg':'seg_en';
(async()=>{const b=await puppeteer.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true,args:["--no-sandbox","--window-size=1920,1080"]});
const p=await b.newPage();await p.setViewport({width:1920,height:1080,deviceScaleFactor:1});
await p.emulateMediaFeatures([{name:'prefers-color-scheme',value:'light'},{name:'prefers-reduced-motion',value:'no-preference'}]);
await p.goto('file://'+process.env.S+'/arch_video/orgalyst.architecture.html',{waitUntil:'load'});await sleep(1200);
await p.click('#btn-present');await sleep(1500);
const chapter=async i=>{const ch=await p.$$('#guided-view-chapters button');await ch[i].click();};
const stop=async i=>{const st=await p.$$('#guided-view-trail [data-story-node]');if(st[i])await st[i].click();};
const runStory=async(ci,n,dur)=>{await sleep(500);await chapter(ci);await sleep(700);const gap=(dur-2.4)/n;for(let i=0;i<n;i++){await stop(i);await sleep(gap*1000);}};
for(const s of script){const dur=s[durKey];const t0=Date.now();const rec=await p.screencast({path:`${outDir}/${s.id}.webm`});
 if(s.id==='a1'){ /* hold with trace motion */ }
 if(s.id==='a2') await runStory(0,7,dur);
 if(s.id==='a3') await runStory(1,8,dur);
 if(s.id==='a4') await runStory(2,4,dur);
 if(s.id==='a5'){await sleep(400);await p.click('#guided-view-all');await sleep(600);const node=await p.$('[data-node-id="mcp"]');await node.click();await sleep(dur*1000*0.42);
   await p.keyboard.press('Escape');await sleep(400);await p.click('#btn-theme');await sleep(dur*1000*0.22);await p.click('#btn-export');await sleep(dur*1000*0.16);await p.keyboard.press('Escape');}
 const remain=dur*1000+400-(Date.now()-t0);if(remain>0)await sleep(remain);await rec.stop();console.log(LANG,s.id,'recorded',((Date.now()-t0)/1000).toFixed(1),'s');
 if(s.id==='a5'){await p.click('#btn-theme');await sleep(300);} }
await p.screenshot({path:`${outDir}/final.png`});await b.close();})();
