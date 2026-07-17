"""Distill submissions.csv into a final workshop schedule.

Run after submissions close: python distill_results.py

Algorithm:
1. Keep only the latest submission per person (by timestamp), so someone
   who submitted more than once only counts once.
2. Tally, for each slot, how many people placed each topic there.
3. A topic can only be scheduled in one slot. Assign topics to slots by
   processing (slot, topic, vote count) triples from the highest vote
   count down. Within a tier, repeatedly resolve any pair that's
   unambiguous — the slot has only one live candidate left, and that
   topic isn't also the top pick for another slot at the same count —
   which cascades as pairs get resolved. This means a topic's strongest
   slot claims it first, and a slot-level tie is broken in favor of
   whichever candidate hasn't already won elsewhere.
4. Whatever's still ambiguous after that (a genuine tie with no vote
   count or already-won distinction to break it) can optionally be
   broken by one or both of:
     --designate NAME       that person's own picks decide any remaining
                             tie their pick is part of. Safe by
                             construction: one person's submission never
                             suggests the same topic for two slots. No
                             fallback — if their pick for a slot isn't
                             live, that slot just stays a tie.
     --rotation {chronological,random}
                             each slot's natural turn-holder is fixed by
                             its own position in the queue (submission
                             order, or shuffled with --seed for a
                             reproducible shuffle) — not shifted by how
                             earlier slots were resolved. If that
                             person's pick for this slot isn't live,
                             search forward through the rest of the
                             rotation (wrapping around) for the next
                             person who does have a live pick here. This
                             resolves almost every remaining tie.
5. Anything still unresolved falls into one of two honest outcomes,
   never guessed at:
     TIE           two or more of the original candidates are still
                   genuinely available and nothing broke the tie.
     NO_CANDIDATE  every topic that ever got a vote for this slot ended
                   up winning a different slot instead — there's
                   nothing left from the original votes to assign here,
                   and it needs a fresh decision.
"""

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

from data.topics import TOPICS

CSV_PATH = Path(__file__).parent / "submissions.csv"
RESULTS_PATH = Path(__file__).parent / "results.csv"

TOPIC_FULL_BY_SHORT = {t["short"]: t["full"] for t in TOPICS}


def load_latest_submissions():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        slot_columns = reader.fieldnames[2:]

    latest_by_name = {}
    for row in rows:
        key = row["name"].strip().lower()
        if not key:
            continue
        existing = latest_by_name.get(key)
        if existing is None or row["timestamp_utc"] > existing["timestamp_utc"]:
            latest_by_name[key] = row
    return list(latest_by_name.values()), slot_columns


def tally_votes(submissions, slot_columns):
    tally = {slot: defaultdict(int) for slot in slot_columns}
    for row in submissions:
        for slot in slot_columns:
            tally[slot][row[slot]] += 1
    return tally


def assign_winners(tally):
    tiers = defaultdict(list)  # count -> list of (slot, topic)
    for slot, topic_counts in tally.items():
        for topic, count in topic_counts.items():
            tiers[count].append((slot, topic))

    winners = {}      # slot -> (topic, count, note)
    unresolved = {}    # slot -> list of (topic, count) tied candidates
    used_topics = set()
    decided_slots = set()

    for count in sorted(tiers.keys(), reverse=True):
        live = [
            (slot, topic) for slot, topic in tiers[count]
            if slot not in decided_slots and slot not in unresolved and topic not in used_topics
        ]

        changed = True
        while changed and live:
            changed = False
            slot_candidates = defaultdict(list)
            topic_claimants = defaultdict(list)
            for slot, topic in live:
                slot_candidates[slot].append(topic)
                topic_claimants[topic].append(slot)

            resolved = [
                (slot, topic) for slot, topic in live
                if len(slot_candidates[slot]) == 1 and len(topic_claimants[topic]) == 1
            ]

            if resolved:
                for slot, topic in resolved:
                    winners[slot] = (topic, count, "top vote")
                    decided_slots.add(slot)
                    used_topics.add(topic)
                live = [(s, t) for s, t in live if s not in decided_slots and t not in used_topics]
                changed = True

        remaining = defaultdict(list)
        for slot, topic in live:
            remaining[slot].append((topic, count))
        for slot, candidates in remaining.items():
            unresolved[slot] = candidates
            decided_slots.add(slot)

    return winners, unresolved


def find_submitter_picks(submissions, slot_columns, name):
    """Return {slot: topic} for the submission matching name (case/whitespace-insensitive), or None."""
    key = name.strip().lower()
    for row in submissions:
        if row["name"].strip().lower() == key:
            return {slot: row[slot] for slot in slot_columns}
    return None


def ordered_submitter_picks(submissions, slot_columns, order, seed=None):
    """Return [(name, {slot: topic}), ...] in submission order or shuffled."""
    people = [
        (row["name"], row["timestamp_utc"], {slot: row[slot] for slot in slot_columns})
        for row in submissions
    ]
    if order == "chronological":
        people.sort(key=lambda p: p[1])
    elif order == "random":
        random.Random(seed).shuffle(people)
    else:
        raise ValueError(f"Unknown order: {order}")
    return [(name, picks) for name, _, picks in people]


def apply_designate_tiebreak(unresolved, winners, used_topics, designate_name, picks, slot_order):
    resolved_count = 0
    for slot in slot_order:
        candidates = unresolved.get(slot)
        if not candidates:
            continue
        pick = picks.get(slot)
        live = {topic for topic, count in candidates}
        if pick in live and pick not in used_topics:
            count = dict(candidates)[pick]
            winners[slot] = (pick, count, f"tie-break: {designate_name}")
            used_topics.add(pick)
            del unresolved[slot]
            resolved_count += 1
    return resolved_count


def apply_rotation_tiebreak(unresolved, winners, used_topics, ordered_people, slot_order):
    """Each slot's natural turn-holder is ordered_people[slot_position % n] — fixed by the
    slot's own position, not shifted by how earlier slots were resolved. If that person's
    pick for this slot isn't live, search forward (wrapping) for the next person in the
    rotation who does have a live candidate here; the next slot still starts from its own
    natural position, not from wherever this search happened to land."""
    open_slots = [slot for slot in slot_order if unresolved.get(slot)]
    resolved_count = 0
    n = len(ordered_people)
    for i, slot in enumerate(open_slots):
        candidates = unresolved.get(slot)
        if not candidates:
            continue
        live = {topic for topic, count in candidates}
        natural_idx = i % n
        for step in range(n):
            name, picks = ordered_people[(natural_idx + step) % n]
            pick = picks.get(slot)
            if pick in live and pick not in used_topics:
                count = dict(candidates)[pick]
                winners[slot] = (pick, count, f"tie-break: {name}'s turn")
                used_topics.add(pick)
                del unresolved[slot]
                resolved_count += 1
                break
    return resolved_count


def parse_args():
    parser = argparse.ArgumentParser(description="Distill submissions.csv into a final schedule.")
    parser.add_argument(
        "--designate", metavar="NAME",
        help="Break remaining ties using this person's own picks wherever they're a live candidate.",
    )
    parser.add_argument(
        "--rotation", choices=["chronological", "random"],
        help="After --designate (if given), break remaining ties by cycling tie-breaking turns "
             "across every submitter, one still-open slot per turn.",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for --rotation random, so the shuffle order can be reproduced later.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not CSV_PATH.exists():
        print(f"No submissions.csv found at {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    submissions, slot_columns = load_latest_submissions()
    if not submissions:
        print("No submissions found.")
        return

    print(f"{len(submissions)} unique submitter(s) after de-duplication.\n")

    tally = tally_votes(submissions, slot_columns)
    winners, unresolved = assign_winners(tally)
    used_topics = {topic for topic, count, note in winners.values()}

    if args.designate:
        picks = find_submitter_picks(submissions, slot_columns, args.designate)
        if picks is None:
            print(f"No submission found for --designate '{args.designate}'.", file=sys.stderr)
            sys.exit(1)
        resolved_count = apply_designate_tiebreak(
            unresolved, winners, used_topics, args.designate, picks, slot_columns
        )
        print(f"Designate tie-break ({args.designate}) resolved {resolved_count} slot(s).\n")

    if args.rotation:
        ordered_people = ordered_submitter_picks(submissions, slot_columns, args.rotation, args.seed)
        resolved_count = apply_rotation_tiebreak(unresolved, winners, used_topics, ordered_people, slot_columns)
        seed_note = f" (seed={args.seed})" if args.rotation == "random" else ""
        print(f"Rotation tie-break ({args.rotation}{seed_note}) resolved {resolved_count} slot(s).\n")

    # A candidate recorded for a slot can be claimed by a *different* slot
    # after this one was tallied (a stronger vote count elsewhere, or a
    # later tie-break pass) — drop anything no longer actually available
    # so the report never lists an already-claimed topic as if it were
    # still pickable.
    for slot in list(unresolved.keys()):
        unresolved[slot] = [(t, c) for t, c in unresolved[slot] if t not in used_topics]

    # Any slot whose only candidates all got claimed by stronger slots
    # elsewhere never enters `winners` or `unresolved` — flag it explicitly.
    for slot in slot_columns:
        if slot not in winners and slot not in unresolved:
            unresolved[slot] = []

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["slot", "status", "topic_short", "topic_full", "votes", "total_votes_for_slot", "note"])
        for slot in slot_columns:
            total = sum(tally[slot].values())
            if slot in winners:
                topic, count, note = winners[slot]
                writer.writerow([slot, "WINNER", topic, TOPIC_FULL_BY_SHORT.get(topic, ""), count, total, note])
            elif unresolved[slot]:
                for topic, count in sorted(unresolved[slot], key=lambda x: -x[1]):
                    writer.writerow([slot, "TIE", topic, TOPIC_FULL_BY_SHORT.get(topic, ""), count, total, ""])
            else:
                writer.writerow([slot, "NO_CANDIDATE", "", "", "", total, ""])

    print("=== WINNERS ===")
    for slot in slot_columns:
        if slot in winners:
            topic, count, note = winners[slot]
            suffix = f" [{note}]" if note != "top vote" else ""
            print(f"  {slot}: {topic} ({count}/{sum(tally[slot].values())} votes){suffix}")

    ties = {slot: cands for slot, cands in unresolved.items() if cands}
    if ties:
        print("\n=== TIES NEEDING A DECISION ===")
        for slot in slot_columns:
            if slot in ties:
                cand_str = ", ".join(f"{t} ({c})" for t, c in ties[slot])
                print(f"  {slot}: {cand_str}")

    no_candidate = [slot for slot in slot_columns if slot in unresolved and not unresolved[slot]]
    if no_candidate:
        print("\n=== NO CANDIDATE LEFT (all voted topics already won elsewhere) ===")
        for slot in no_candidate:
            print(f"  {slot}")

    print(f"\nFull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
