# fridge_magnets

A drag-and-drop board for building a workshop schedule. Each of the 29 topic
tiles gets dragged into exactly one room slot across the Friday/Saturday grid
(9 + 20 = 29 slots). Contributors enter their name and submit their proposed
arrangement; every submission is appended as a row to `submissions.csv`.

Tap or click a tile to see its full title; the short version is what's shown
on the tile itself.

## Running locally (development)

After cloning onto a new machine, set up the virtual environment once:

```bash
./setup.sh
```

(This just runs `python3 -m venv .venv` and `pip install -r requirements.txt`
— run those two commands by hand instead if you'd rather not run a script.)

Then, each time you want to run it:

```bash
source .venv/bin/activate
python app.py
```

Visit http://localhost:5000. `submissions.csv` is created in the project
root the first time someone submits.

## Running for the event (self-hosted, port-forwarded)

The dev server above isn't meant to sit behind a public port forward. Use
the included `waitress` production server instead:

```bash
source .venv/bin/activate
python serve.py
```

This serves on port 8080. Forward that port on your router to this machine,
then share your public IP (or a dynamic DNS hostname if you have one) with
attendees. A few notes since this will be reachable from the internet:

- There's no login — anyone with the link can submit. That's expected here
  since it's a casual per-person scheduling tool, not an authenticated system.
- Only forward the port while the event is actually running, and close it
  afterward.
- `submissions.csv` lives on this machine, in the project root. Back it up
  periodically if the event runs over multiple days.

## Editing topics or the time grid

- `data/topics.py` — the 29 topics (`id`, `short` tile label, `full` title).
- `data/schedule.py` — the time blocks and how many rooms run in each.

The app requires the total number of room-slots to exactly match the number
of topics, since every tile must be placed and every slot must be filled
before a submission is accepted.

## Submissions format

`submissions.csv` has one row per submission: a UTC timestamp, the
submitter's name, then one column per slot (labeled `<Day> <time> — Room N`)
containing the short name of the topic they placed there.

## Distilling a final schedule

Once submissions are in, run:

```bash
source .venv/bin/activate
python distill_results.py
```

This reads `submissions.csv` and writes `results.csv` alongside it, plus
prints a summary. It:

1. Keeps only each person's most recent submission (by timestamp) if they
   submitted more than once.
2. Tallies, per slot, how many people placed each topic there.
3. Assigns each topic to its strongest-supporting slot — a topic can only
   win one slot, so if it's the top pick in more than one, it goes to
   whichever slot voted for it the most, and the other slot(s) fall back to
   their next-best options.
4. Breaks a tie within a slot by preferring whichever tied topic hasn't
   already won a different slot.
5. Anything still ambiguous after that (a genuine tie with no vote-count or
   already-won distinction to break it) is left as a `TIE` row — unless one
   of the optional tie-break flags below is used.

`results.csv` has one row per slot: `WINNER` (with its topic, vote count,
and a `note` on how it was decided), `TIE` (one row per candidate still
genuinely available and tied), or `NO_CANDIDATE` — every topic that ever
got a vote for that slot ended up winning a different slot instead, so
there's nothing left from the original votes to assign there.

### Optional: breaking remaining ties

```bash
python distill_results.py --designate "Gregory"
python distill_results.py --rotation chronological
python distill_results.py --rotation random --seed 42
python distill_results.py --designate "Gregory" --rotation chronological
```

- `--designate NAME` — for any slot still tied, if that person's own pick
  for that slot is one of the tied candidates, it wins. Safe by
  construction: one person's submission never places the same topic in two
  slots, so their picks can't create a new conflict. No fallback — if their
  pick for a slot isn't available, that slot just stays a `TIE`.
- `--rotation {chronological,random}` — each slot's natural turn-holder is
  fixed by its own position in the queue (submission order, or shuffled
  with `--seed N` for a reproducible shuffle) — not shifted by how earlier
  slots were resolved. If that person's pick isn't available, it searches
  forward through the rest of the rotation for the next person who does
  have a live pick for that specific slot. This resolves almost every
  remaining tie in practice — what's left afterward is usually
  `NO_CANDIDATE` (every original option for that slot won elsewhere)
  rather than a real `TIE`.
- Both flags can be combined — `--designate` runs first, then `--rotation`
  mops up whatever's still open. Note this doesn't strictly do better than
  `--rotation` alone: spending a designate's picks first can use up a
  topic in an order that leaves fewer slots resolvable overall than letting
  rotation handle everything itself. Worth comparing both on your real
  data rather than assuming combined is always best.
- Whatever's left after all of that is written as `TIE` or `NO_CANDIDATE`
  for a human to make the final call on.
