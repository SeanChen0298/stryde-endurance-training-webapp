# Stryde Roadmap — to 31 Dec 2026

The planner bot reads this file top to bottom and plans the first milestone that isn't done.
A step marked **OWNER** waits for the repo owner. Plan nothing past an unticked OWNER step
in the same milestone.

## M0 — Make the repo ready for bots (owner)

- [x] OWNER: CI runs backend tests and frontend build on every pull request
- [x] OWNER: `main` protected — pull requests only, CI must be green
- [ ] OWNER: this guide (`CLAUDE.md`) and roadmap merged
- [ ] OWNER: rotate `JWT_SECRET` on Railway (an old session cookie was committed)
- [ ] OWNER: bot pipeline set up and one ticket run end to end

## M1 — Garmin as the only data source (bots)

Reference implementation exists on branch `wip/garmin-sync`; read it, don't merge it.

- [ ] Garmin sign-in on `python-garminconnect` 0.3: the library no longer installs `garth`,
      so the current code breaks on the next deploy. Old saved tokens must show "reconnect".
- [ ] Sync runs from Garmin into `activities` (all running sub-types: road, treadmill, trail…)
- [ ] Daily job: last 7 days of activities and 3 days of health. Full backfill
      (1 year of activities, 90 days of health) only on connect or manual sync.
- [ ] Switch Strava off: routes return 410, Strava removed from the connect page, dashboard
      banner and settings; settings offers "delete Strava data"
- [ ] AI paths (brief, plan, readiness load) read only `source = 'garmin'` activities
- [ ] Settings "paste token" option and its helper script use the new token format

Done means: CI green, and the owner sees a fresh Garmin sign-in sync runs and health
(**OWNER** check on the live app).

## M2 — Tests worth gating on (bots)

- [ ] Tests for readiness score calculation
- [ ] Tests for plan revision triggers
- [ ] Tests for plan JSON parsing and validation
- [ ] Snapshot tests for the daily brief and plan prompt builders

## M3 — Planner upgrades (owner + bots, from 27 Nov)

- [ ] Haze forecast (Open-Meteo Air Quality API) as a planner input and a revision trigger
- [ ] Rule checks on Gemini's plan: no hard session on a day forecast above AQI 150,
      no week more than ~10% over the previous one; reject and retry otherwise
- [ ] Small wins: rule-based detection from the athlete's own data, at most one a day,
      dashboard card plus phone notification, Sunday digest

## M4 — Demo (by 31 Dec)

- [ ] Demo mode on saved data
- [ ] Pipeline stats page: merged PRs, first-try pass rate, times a bot asked the owner
- [ ] OWNER: write-up and screen recording

## Not before 31 Dec

More users, Strava, social media tracking, a phone app, nutrition, any new data source.
