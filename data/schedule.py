"""Time blocks for the event. Each block has a number of parallel rooms;
each room in each block is one draggable slot."""

TIME_BLOCKS = [
    {"day": "Friday", "time": "2:00 pm - 3:15 pm", "rooms": 3},
    {"day": "Friday", "time": "3:30 pm - 4:45 pm", "rooms": 3},
    {"day": "Friday", "time": "5:00 pm - 6:15 pm", "rooms": 3},
    {"day": "Saturday", "time": "8:00 am - 9:15 am", "rooms": 4},
    {"day": "Saturday", "time": "9:30 am - 10:45 am", "rooms": 4},
    {"day": "Saturday", "time": "11:00 am - 12:15 pm", "rooms": 4},
    {"day": "Saturday", "time": "1:45 pm - 3:00 pm", "rooms": 4},
    {"day": "Saturday", "time": "3:15 pm - 4:30 pm", "rooms": 4},
]


def build_slots():
    """Flatten TIME_BLOCKS into individual room slots with stable ids and labels."""
    slots = []
    for block_index, block in enumerate(TIME_BLOCKS):
        day_key = block["day"][:3].lower()
        for room in range(1, block["rooms"] + 1):
            slot_id = f"{day_key}-{block_index}-r{room}"
            slots.append({
                "id": slot_id,
                "day": block["day"],
                "time": block["time"],
                "room": room,
                "label": f"{block['day']} {block['time']} — Room {room}",
            })
    return slots


SLOTS = build_slots()
