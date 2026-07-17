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
