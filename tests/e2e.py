from playwright.sync_api import sync_playwright
import re
R=[]  # (name, ok, detail)
def check(name, ok, detail=''):
    R.append((name,bool(ok),detail)); print(('PASS ' if ok else 'FAIL ')+name+(' -- '+str(detail) if detail and not ok else ''))
logs=[]
URL='http://localhost:5173/'
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={'width':900,'height':900})
    page=ctx.new_page()
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}') if m.type in ('error','warning') else None)
    page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))
    cdp=ctx.new_cdp_session(page); cdp.send('WebAuthn.enable')
    cdp.send('WebAuthn.addVirtualAuthenticator',{'options':{'protocol':'ctap2','transport':'internal','hasResidentKey':True,'hasUserVerification':True,'isUserVerified':True,'automaticPresenceSimulation':True}})

    page.goto(URL); page.wait_for_selector('.post')
    check('feed loads 3 posts from API', page.locator('.post').count()==3, page.locator('.post').count())
    check('no offline banner', page.locator('.feed-note:has-text("sample")').count()==0)
    check('logged-out shows Verify button', page.get_by_role('button',name='Verify passkey').count()==1)

    # sort tabs
    page.get_by_role('button',name='By credibility').click()
    first=page.locator('.post-title').first.inner_text()
    check('sort by credibility puts DCI 4.9 post first', 'authorship order' in first, first)
    page.get_by_role('button',name='Most discussed').click()
    check('sort by discussed puts 41 first', 'authorship order' in page.locator('.post-title').first.inner_text())

    # keyboard: Space opens a card
    page.locator('.post').nth(1).focus(); page.keyboard.press('Space')
    page.wait_for_selector('.poll-block')
    check('Space key opens post (hash route)', '#/post/' in page.url, page.url)
    # back button
    page.go_back(); page.wait_for_selector('.post')
    check('Back button returns to feed', page.locator('.post').count()==3)
    page.go_forward(); page.wait_for_selector('.poll-block')
    check('Forward returns to post', True)
    # refresh keeps post
    page.reload(); page.wait_for_selector('.poll-block')
    check('refresh on a post URL keeps the post', page.locator('.detail-title').count()==1)

    # gated poll: open modal then cancel via Escape -> error shown, not "Submitted"
    page.get_by_role('button',name='Submit response').click(); page.wait_for_selector('.modal')
    page.keyboard.press('Escape'); page.wait_for_selector('.modal',state='detached')
    page.wait_for_selector('.poll-error')
    check('cancelled auth shows error, poll NOT submitted', page.get_by_role('button',name='Submit response').count()==1 and 'cancel' in page.locator('.poll-error').inner_text().lower(), page.locator('.poll-error').inner_text())

    # register -> poll auto-submits and shows community aggregate
    page.get_by_role('button',name='Submit response').click(); page.wait_for_selector('.modal')
    page.get_by_text('First time here? Create a passkey').click()
    page.get_by_role('button',name='Create passkey').click()
    try:
        page.wait_for_selector('.poll-community',timeout=8000); ok=True
    except Exception: ok=False
    check('register passkey -> pending poll auto-submits with community view', ok, page.locator('.modal-status').all_inner_texts())
    check('poll shows Submitted', page.get_by_role('button',name='Submitted').count()==1)
    uid=page.locator('.auth-state .blind-uid').inner_text()
    check('header shows Blind_UID', re.match(r'^[0-9a-f]{4}-[0-9a-f]{4}$',uid), uid)

    # session persists across reload
    page.reload(); page.wait_for_selector('.auth-state')
    check('session restored after reload', page.locator('.auth-state .blind-uid').inner_text()==uid)

    # compose: validation
    page.get_by_role('button',name='Submit a post-mortem').click(); page.wait_for_selector('#body')
    check('compose route', page.url.endswith('#/compose'))
    page.fill('#body','too short')
    page.get_by_role('button',name='Run guard & publish').click(); page.wait_for_selector('.guard-note')
    check('short post rejected with reason', 'little more' in page.locator('.guard-note').inner_text())
    page.fill('#body','I enrolled in CS 101 and nobody ever told us when the add deadline moved, which cost me a full semester of fees.')
    page.get_by_role('button',name='Run guard & publish').click()
    page.wait_for_selector('.guard-note:has-text("course code")')
    check('guard rejects course code', True)
    page.fill('#body','Professor Smith never answered a single email about the late submission policy, and there was nowhere to escalate this.')
    page.get_by_role('button',name='Run guard & publish').click()
    page.wait_for_selector('.guard-note:has-text("named individual")')
    check('guard rejects named individual', True)
    good='The late-submission policy lives in three different documents and none of them agree. Students find out which one applies only after a penalty is already applied. One canonical policy page would have prevented this.'
    page.fill('#body',good)
    page.get_by_role('button',name='Run guard & publish').click(); page.wait_for_selector('.post')
    check('publish succeeds and returns to feed', page.locator('.post').count()==4 and page.url.endswith('#/'), page.url)
    check('new post is first in feed', 'late-submission policy' in page.locator('.post-title').first.inner_text(), page.locator('.post-title').first.inner_text())
    page.reload(); page.wait_for_selector('.post')
    check('new post persists after reload (server-side)', page.locator('.post').count()==4)

    # one vote per Blind_UID updates, not duplicates
    page.locator('.post').nth(2).click(); page.wait_for_selector('.poll-block')

    # sign out then sign in with existing passkey
    page.get_by_role('button',name='Sign out').click(); page.wait_for_selector('button:has-text("Verify passkey")')
    page.goto(URL); page.wait_for_selector('.post')
    check('sign out survives reload (cookie cleared)', page.get_by_role('button',name='Verify passkey').count()==1)
    page.get_by_role('button',name='Verify passkey').click(); page.wait_for_selector('.modal')
    page.get_by_role('button',name='Continue with Face ID / Touch ID').click()
    try:
        page.wait_for_selector('.auth-state',timeout=8000); ok=True
    except Exception: ok=False
    check('sign in with existing passkey works', ok, page.locator('.modal-status').all_inner_texts())
    check('same Blind_UID after re-login', page.locator('.auth-state .blind-uid').inner_text()==uid, page.locator('.auth-state .blind-uid').inner_text())

    # compose route while signed out bounces to feed
    page.get_by_role('button',name='Sign out').click()
    page.goto(URL+'#/compose'); page.wait_for_timeout(800)
    check('#/compose while signed out bounces to feed', not page.url.endswith('#/compose') and page.locator('#body').count()==0, page.url)
    page.goto(URL+'#/post/does-not-exist'); page.wait_for_timeout(800)
    check('unknown post shows not-found message', page.locator('.feed-note:has-text("could not be found")').count()==1)

    # visuals
    page.goto(URL); page.wait_for_selector('.post'); page.screenshot(path='/tmp/v_feed.png')
    page.locator('.post').first.click(); page.wait_for_selector('.poll-block'); page.screenshot(path='/tmp/v_detail.png',full_page=True)
    page.emulate_media(color_scheme='dark'); page.screenshot(path='/tmp/v_dark.png')
    page.emulate_media(color_scheme='light')
    page.set_viewport_size({'width':390,'height':800}); page.screenshot(path='/tmp/v_mobile.png')
    ov=page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    check('no horizontal overflow on mobile', not ov)
    b.close()
print('\nconsole errors/warnings:'); print('\n'.join(sorted(set(logs))) or '(none)')
f=[r for r in R if not r[1]]; print(f'\n{len(R)-len(f)}/{len(R)} passed')
