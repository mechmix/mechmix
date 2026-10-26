import argparse,json,pathlib,time
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=pathlib.Path(args.folder)
deadline=time.monotonic()+400
while not (root/'server-ready.txt').exists():
 if (root/'exit-code.txt').exists():
  raise RuntimeError('Native standard-user checks ended before browser startup. Inspect the generated verification report.')
 if time.monotonic()>deadline:raise RuntimeError('Native standard-user server did not become ready')
 time.sleep(1)
try:
 with sync_playwright() as play:
  browser=play.chromium.launch();page=browser.new_page(viewport={'width':1100,'height':1000})
  page.goto((root/'ui-url.txt').read_text());page.get_by_role('button',name='Choose files',exact=True).wait_for()
  page.locator('#picker').set_input_files(str(root/'fixtures/generated.vsdx'))
  page.get_by_text('Saved to Downloads',exact=False).first.wait_for(timeout=180000)
  page.screenshot(path=str(root/'browser-conversion.png'),full_page=True)
  assert not page.locator('.row.error').count()
  browser.close()
 (root/'browser-verification.json').write_text(json.dumps({'passed':True,'upload_vsdx':True}))
finally:(root/'ui-finished.txt').write_text('finished')
