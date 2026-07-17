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
   count or already-won distinction to break it) is left unresolved for
   a human to decide, rather than guessed at.
"""

import csv
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

    winners = {}      # slot -> (topic, count)
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
                    winners[slot] = (topic, count)
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


def main():
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

    # Any slot whose only candidates all got claimed by stronger slots
    # elsewhere never enters `winners` or `unresolved` — flag it explicitly.
    for slot in slot_columns:
        if slot not in winners and slot not in unresolved:
            unresolved[slot] = []

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["slot", "status", "topic_short", "topic_full", "votes", "total_votes_for_slot"])
        for slot in slot_columns:
            total = sum(tally[slot].values())
            if slot in winners:
                topic, count = winners[slot]
                writer.writerow([slot, "WINNER", topic, TOPIC_FULL_BY_SHORT.get(topic, ""), count, total])
            elif unresolved[slot]:
                for topic, count in sorted(unresolved[slot], key=lambda x: -x[1]):
                    writer.writerow([slot, "TIE", topic, TOPIC_FULL_BY_SHORT.get(topic, ""), count, total])
            else:
                writer.writerow([slot, "NO_CANDIDATE", "", "", "", total])

    print("=== WINNERS ===")
    for slot in slot_columns:
        if slot in winners:
            topic, count = winners[slot]
            print(f"  {slot}: {topic} ({count}/{sum(tally[slot].values())} votes)")

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
