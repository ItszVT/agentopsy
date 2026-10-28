// Read-only checks against the locally prepared, pinned 1,000-run demo.
const {chromium}=require(process.env.AGENTOPSY_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const base=process.env.AGENTOPSY_URL||'http://127.0.0.1:8767';
(async()=>{
 const browser=await chromium.launch({channel:process.env.AGENTOPSY_BROWSER||'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.getByText('New to Agentopsy? Start here.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Import traces',exact:false}).count(),0);
  assert.equal(await page.locator('#file-picker').count(),0);
  const health=await(await page.request.get(base+'/api/health')).json();
  assert.equal(health.read_only,true);
  assert.equal(health.source_url,'https://huggingface.co/datasets/NJU-LINK/CodeTraceBench');
  assert.equal(health.dataset_license,'MIT');
  await page.getByRole('link',{name:'License notices',exact:false}).waitFor();
  await page.getByRole('link',{name:'Research citation',exact:false}).waitFor();
  const notices=await page.request.get(base+health.notices_url);
  assert.equal(notices.status(),200);
  assert.match(await notices.text(),/CodeTraceBench/);
  const overview=await(await page.request.get(base+'/api/overview')).json();
  assert.deepEqual([overview.total,overview.solved,overview.failed,overview.unknown],[1000,504,468,28]);
  assert.equal((await page.request.post(base+'/api/import',{data:'ignored'})).status(),403);
  assert.equal((await page.request.delete(base+'/api/demo')).status(),403);
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(process.env.AGENTOPSY_SCREENSHOTS)await page.screenshot({path:`${process.env.AGENTOPSY_SCREENSHOTS}/demo-${width}.png`});
  }
  await page.locator('nav').getByRole('button',{name:'Case files'}).click();
  await page.getByLabel('Filter outcomes').selectOption('unverified');
  assert.match(await page.locator('.filter-count').innerText(),/28 CASES/);
  await page.locator('tbody tr[data-id]').first().click();
  await page.locator('.case-detail-grid').waitFor();
  assert.match(await page.locator('#view').innerText(),/Outcome not independently verified/);
  for(const name of ['The Findings','Agent Performance Lab','Failure Lab','Overview']){
   await page.locator('nav').getByRole('button',{name,exact:false}).click();
   await page.locator('#view h1').waitFor();
  }
  assert.equal((await page.request.get(base+'/api/cases/does-not-exist')).status(),404);
  assert.deepEqual(errors,[]);
  console.log('Demo browser checks passed: real cohort, 28 unverified outcomes, disabled writes, onboarding, navigation, 3 widths, no JS errors.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
