// Optional read-only browser smoke test. Install Playwright separately; see README.
const {chromium} = require(process.env.AGENTOPSY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const base = process.env.AGENTOPSY_URL || 'http://127.0.0.1:8766';
(async () => {
  const browser = await chromium.launch({channel:process.env.AGENTOPSY_BROWSER || 'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    const navigate = async () => {
      await page.locator('nav').getByRole('button',{name:'Failure Lab'}).click();
      await page.locator('.fl-scope').waitFor();
    };
    const update = async action => {
      const response = page.waitForResponse(r => r.url().includes('/api/failure-lab') && r.status()===200);
      await action();
      const data = await (await response).json();
      await page.locator('.fl-scope').waitFor();
      assert.match(await page.locator('.fl-scope').innerText(), new RegExp(`${data.total.toLocaleString('en-US')} imported runs selected`));
      return data;
    };
    await navigate();
    const data = await (await page.request.get(base+'/api/failure-lab')).json();
    assert.match(await page.locator('.fl-scope').innerText(),/imported runs selected/);
    if(data.total) {
      const category = data.categories.find(c => c.verified && c.steps.solved.count && c.steps.unsolved.count);
      if(category) {
        await update(() => page.getByLabel('Task category',{exact:true}).selectOption(category.category));
        assert.equal(await page.locator('.fl-category').count(),1);
        const groupAgent=category.agents.find(a=>a.verified).agent;
        await update(() => page.getByLabel('Agent',{exact:true}).selectOption(groupAgent));
        await update(() => page.getByRole('button',{name:'Reset all filters',exact:true}).click());
        await update(() => page.getByLabel('Task category',{exact:true}).selectOption(category.category));
        const support = page.locator('.fl-insight .fl-support').first();
        if(await support.count()) {
          await support.locator('summary').click();
          await support.locator('[data-case]').first().click();
          await page.getByRole('button',{name:'BACK TO FAILURE LAB',exact:false}).click();
          await page.locator('.fl-scope').waitFor();
          assert.equal(await page.getByLabel('Task category',{exact:true}).inputValue(),category.category);
        }
        await update(() => page.locator('.fl-bar-row').first().click());
        assert.match(await page.locator('.notice').first().innerText(),/Outcome filtering is active/);
        await update(() => page.getByRole('button',{name:'Reset all filters',exact:true}).click());
      }
      const pattern = data.patterns[0];
      if(pattern) {
        await update(() => page.getByLabel('Evidence signal',{exact:true}).selectOption(pattern.name));
        await update(() => page.getByRole('button',{name:'Reset all filters',exact:true}).click());
      }
      await page.getByLabel('Minimum steps',{exact:true}).fill('25');
      await page.getByLabel('Maximum steps',{exact:true}).fill('99');
      const bounded=await update(() => page.getByRole('button',{name:'Apply step range'}).click());
      assert.ok(bounded.cases.every(c=>c.steps>=25 && c.steps<=99));
      await page.getByLabel('Minimum steps',{exact:true}).fill('100');
      await page.getByRole('button',{name:'Apply step range'}).click();
      assert.ok(await page.getByLabel('Maximum steps',{exact:true}).evaluate(el=>!el.validity.valid));
      await update(() => page.getByRole('button',{name:'Reset all filters',exact:true}).click());
      for(const width of [1440,768,390]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        if(process.env.AGENTOPSY_SCREENSHOTS) await page.screenshot({path:`${process.env.AGENTOPSY_SCREENSHOTS}/failure-${width}.png`});
      }
    }
    const empty={...data,total:0,verified:0,excluded:0,cases:[],categories:[],patterns:[],insights:[],sources:{}};
    await page.route('**/api/failure-lab**',route=>route.fulfill({json:empty}));
    await navigate();
    await page.getByText('No imported runs match this investigation.',{exact:true}).waitFor();
    await page.unroute('**/api/failure-lab**');
    await page.route('**/api/failure-lab**',route=>route.fulfill({status:500,json:{detail:'Test unavailable'}}));
    await page.locator('nav').getByRole('button',{name:'Failure Lab'}).click();
    await page.getByText('Could not load Failure Lab',{exact:true}).waitFor();
    await page.unroute('**/api/failure-lab**');
    await page.getByRole('button',{name:'Try again'}).click();
    await page.locator('.fl-scope').waitFor();
    for(const name of ['Overview','Case files','Pattern lab','Agent Performance Lab','Import traces']) {
      await page.locator('nav').getByRole('button',{name,exact:false}).click();
      await page.locator('#view h1').waitFor();
    }
    assert.deepEqual(errors,[]);
    console.log('Browser checks passed: filters, ranges, chart drill-down, case return, empty/error states, 3 widths, existing navigation, no JS errors.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1)});
