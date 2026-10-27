"""Extra coverage that tests/e2e.py does not exercise:
   1. offline fallback: GET /api/posts blocked -> sample posts + banner, Retry recovers
   2. poll rules: first response increments "found this useful"; resubmitting from the
      same Blind_UID updates the response without double-counting
   Run with the dev server (`npm run dev`) up, same as tests/e2e.py.
"""
from playwright.sync_api import sync_playwright

R = []  # (name, ok, detail)
def check(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' -- ' + str(detail)) if detail and not ok else ''))

logs = []
URL = 'http://localhost:5173/'
blocked = {'on': False}

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 900, 'height': 900})
    page = ctx.new_page()
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
    page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))

    def route(route_):
        if blocked['on'] and route_.request.method == 'GET' and '/api/posts' in route_.request.url:
            return route_.abort()
        route_.continue_()
    page.route('**/*', route)

    # ---- 1. offline fallback ----
    blocked['on'] = True
    page.goto(URL)
    page.wait_for_selector('.feed-note')
    note = page.locator('.feed-note').inner_text()
    check('offline banner shown when API unreachable', 'sample posts' in note, note)
    check('sample posts still rendered', page.locator('.post').count() == 3, page.locator('.post').count())
    blocked['on'] = False
    page.get_by_role('button', name='Retry').click()
    page.wait_for_selector('.post')
    page.wait_for_timeout(400)
    check('Retry recovers the live feed from the API',
          page.locator('.feed-note:has-text("sample")').count() == 0)

    # ---- 2. poll: one response per Blind_UID ----
    cdp = ctx.new_cdp_session(page)
    cdp.send('WebAuthn.enable')
    cdp.send('WebAuthn.addVirtualAuthenticator', {'options': {
        'protocol': 'ctap2', 'transport': 'internal', 'hasResidentKey': True,
        'hasUserVerification': True, 'isUserVerified': True, 'automaticPresenceSimulation': True}})

    page.get_by_role('button', name='Verify passkey').click()
    page.wait_for_selector('.modal')
    page.get_by_text('First time here? Create a passkey').click()
    page.get_by_role('button', name='Create passkey').click()
    page.wait_for_selector('.auth-state', timeout=8000)

    page.get_by_role('button', name='Most discussed').click()
    page.locator('.post').first.click()
    page.wait_for_selector('.poll-block')
    before = page.locator('.post-foot span').nth(1).inner_text()

    page.get_by_role('button', name='Submit response').click()
    page.wait_for_selector('.poll-community', timeout=8000)
    page.wait_for_timeout(500)
    after = page.locator('.post-foot span').nth(1).inner_text()
    check('first response increments "found this useful"', before != after, f'{before} -> {after}')
    check('community aggregate shown after submit', page.locator('.poll-community').count() > 0)
    check('poll shows Submitted', page.get_by_role('button', name='Submitted').count() == 1)
    n1 = int(after.split()[0])

    # Same Blind_UID posts a second response (server must update, not double-count).
    post_id = page.url.split('#/post/')[1]
    status = page.evaluate("""async (postId) => {
      const r = await fetch('/api/posts/' + encodeURIComponent(postId) + '/poll', {
        method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({responses: {independence: 10, speed: 90, disruption: 50,
                                           reach: 10, noise: 90, cost: 50,
                                           fairness: 10, flexibility: 90, overhead: 50}})
      });
      return r.status;
    }""", post_id)
    check('second response from same Blind_UID accepted', status == 200, status)
    page.reload()
    page.wait_for_selector('.poll-block')
    again = page.locator('.post-foot span').nth(1).inner_text()
    n2 = int(again.split()[0])
    check('resubmitting does not double-count the lesson tally', n2 == n1, f'{after} -> {again}')

    b.close()

print('\nconsole errors/warnings:')
print('\n'.join(sorted(set(logs))) or '(none)')
f = [r for r in R if not r[1]]
print(f'\n{len(R) - len(f)}/{len(R)} passed')
