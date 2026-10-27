// Read-only optional browser validation; uses the same setup as browser_failure.cjs.
const {chromium}=require(process.env.AGENTOPSY_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const base=process.env.AGENTOPSY_URL||'http://127.0.0.1:8766';
(async()=>{
 const browser=await chromium.launch({channel:process.env.AGENTOPSY_BROWSER||'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  const navigate=async()=>{await page.locator('nav').getByRole('button',{name:'The Findings'}).click();await page.locator('.research-scope').waitFor()};
  const update=async(action)=>{const [response]=await Promise.all([page.waitForResponse(r=>r.url().includes('/api/findings')&&r.status()===200),action()]);const data=await response.json();await page.locator('.research-scope').waitFor();assert.match(await page.locator('.research-scope').innerText(),new RegExp(`${data.total.toLocaleString('en-US')} Tracebench runs`));return data};
  await navigate();
  const data=await(await page.request.get(base+'/api/findings')).json();
  if(data.findings.length){
   const finding=data.findings[0];
   await update(()=>page.getByLabel('Research category',{exact:true}).selectOption(finding.category));
   const card=page.locator('.research-card').first();
   await card.locator('.research-support summary').click();
   await card.locator('[data-case]').first().waitFor();
   assert.equal(await card.locator('[data-case]').count(),finding.sample_size);
   await card.locator('[data-case]').first().click();
   await page.getByRole('button',{name:'BACK TO THE FINDINGS',exact:false}).click();
   await page.locator('.research-scope').waitFor();
   assert.equal(await page.getByLabel('Research category',{exact:true}).inputValue(),finding.category);
   await update(()=>page.getByLabel('Research agent',{exact:true}).selectOption(data.options.agent[0]));
   await update(()=>page.getByRole('button',{name:'Reset findings filters'}).click());
  }
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(process.env.AGENTOPSY_SCREENSHOTS)await page.screenshot({path:`${process.env.AGENTOPSY_SCREENSHOTS}/research-${width}.png`});
  }
  const empty={...data,total:0,solved:0,unsolved:0,verified:0,unverified:0,success_rate:null,findings:[],cases:[],audited_rows:0,manifests:[],coverage:{explicit_zero:0,positive:0,missing:0,invalid:0,legacy_unknown:0}};
  await page.route('**/api/findings**',route=>route.fulfill({json:empty}));
  await navigate();await page.getByText('No imported Tracebench records match.',{exact:true}).waitFor();
  await page.unroute('**/api/findings**');
  await page.route('**/api/findings**',route=>route.fulfill({status:500,json:{detail:'Test unavailable'}}));
  await page.locator('nav').getByRole('button',{name:'The Findings'}).click();
  await page.getByText('Could not load The Findings',{exact:true}).waitFor();
  await page.unroute('**/api/findings**');
  await page.getByRole('button',{name:'Try again'}).click();await page.locator('.research-scope').waitFor();
  for(const name of ['Overview','Case files','Pattern lab','Agent Performance Lab','Failure Lab','Import traces']){
   await page.locator('nav').getByRole('button',{name,exact:false}).click();await page.locator('#view h1').waitFor();
  }
  assert.deepEqual(errors,[]);
  console.log('Research browser checks passed: calculated data, filters, supporting cases and return, empty/error states, 3 widths, existing navigation, no JS errors.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
