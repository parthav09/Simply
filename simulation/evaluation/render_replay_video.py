"""Render a recorded run to an MP4 for presentations.

Draws only what the saved recording contains (positions, actions, carts);
nothing is simulated or invented here. Needs Pillow and ffmpeg.

    python3 simulation/evaluation/render_replay_video.py <published-run.json> <out.mp4> [--fps 20]
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, CELL, MAP_X, MAP_Y = 1280, 720, 40, 24, 96
BG, FLOOR, INK, MUTED = (247, 243, 232), (236, 229, 210), (38, 36, 30), (120, 114, 98)
DEPT = {'Meat & Seafood': (214, 150, 140), 'Ramen & Noodles': (222, 190, 110), 'Dairy & Eggs': (150, 178, 210),
        'Prepared Meals': (214, 160, 110), 'Health & Beauty': (214, 150, 170), 'Pet': (190, 150, 120),
        'Produce': (150, 190, 140), 'Pantry': (214, 180, 120), 'Frozen': (150, 195, 205), 'Baby': (225, 170, 180),
        'Snacks': (218, 165, 110), 'Bakery': (220, 185, 130), 'Beverages': (140, 165, 205), 'Household': (150, 185, 165)}
PALETTE = [(200, 70, 60), (60, 120, 200), (60, 160, 100), (170, 90, 190), (230, 140, 40),
           (40, 160, 170), (200, 80, 140), (110, 110, 60), (90, 90, 190), (150, 100, 60)]
IMPULSE, BAD = (214, 120, 20), (190, 40, 40)


def font(size, bold=False):
    return ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size, index=1 if bold else 0)


def load(path):
    bundle = json.loads(Path(path).read_text())
    return json.loads(bundle['payload_json'])


def draw_map(d, layout, positions, shoppers, trail):
    d.rounded_rectangle([MAP_X - 8, MAP_Y - 8, MAP_X + layout['width'] * CELL + 8, MAP_Y + layout['height'] * CELL + 8],
                        12, fill=FLOOR)
    for shelf in layout['shelves']:
        colour = DEPT.get(shelf['department'], (200, 190, 170))
        for dx, dy in shelf['offsets']:
            x, y = MAP_X + (shelf['x'] + dx) * CELL, MAP_Y + (shelf['y'] + dy) * CELL
            d.rounded_rectangle([x + 2, y + 2, x + CELL - 2, y + CELL - 2], 6, fill=colour)
        d.text((MAP_X + shelf['x'] * CELL, MAP_Y + shelf['y'] * CELL - 16), shelf['department'], font=font(11), fill=MUTED)
    for x, y in layout['entrance']:
        d.rectangle([MAP_X + x * CELL + 4, MAP_Y + y * CELL + 4, MAP_X + x * CELL + CELL - 4, MAP_Y + y * CELL + CELL - 4],
                    fill=(176, 206, 170))
    for x, y in layout['checkout']:
        d.rectangle([MAP_X + x * CELL + 4, MAP_Y + y * CELL + 4, MAP_X + x * CELL + CELL - 4, MAP_Y + y * CELL + CELL - 4],
                    fill=(205, 170, 110))
    d.text((MAP_X + layout['entrance'][0][0] * CELL, MAP_Y + layout['entrance'][0][1] * CELL - 16), 'ENTRANCE', font=font(11), fill=MUTED)
    d.text((MAP_X + layout['checkout'][0][0] * CELL, MAP_Y + layout['checkout'][0][1] * CELL - 16), 'CHECKOUT', font=font(11), fill=MUTED)
    for index, shopper in enumerate(shoppers):
        for x, y in trail.get(shopper['id'], [])[-12:]:
            cx, cy = MAP_X + x * CELL + CELL // 2, MAP_Y + y * CELL + CELL // 2
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=PALETTE[index % 10] + ())
    for index, shopper in enumerate(shoppers):
        pos = positions[shopper['id']]
        cx, cy = MAP_X + pos['x'] * CELL + CELL // 2, MAP_Y + pos['y'] * CELL + CELL // 2
        r = 13
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PALETTE[index % 10], outline=INK if pos['phase'] != 'FinishedState' else (90, 160, 90), width=2)
        d.text((cx, cy), shopper['name'].split()[0][0], font=font(13, True), fill=(255, 255, 255), anchor='mm')


def frame(run, shoppers, positions, trail, event, stats, index_by_id, total):
    image = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(image)
    source = run['source']
    d.text((24, 22), f"Simply · {run['layout']['id'].replace('_', ' ')}", font=font(24, True), fill=INK)
    d.text((24, 56), f"{source['model']} · {source['provider']} · recorded {source['recorded_at'][:10]}", font=font(14), fill=MUTED)
    draw_map(d, run['layout'], positions, shoppers, trail)
    px = MAP_X + run['layout']['width'] * CELL + 40
    d.text((px, 96), f"Decision {stats['n']} / {total}", font=font(18, True), fill=INK)
    bar_w = W - px - 24
    d.rounded_rectangle([px, 126, px + bar_w, 134], 4, fill=FLOOR)
    d.rounded_rectangle([px, 126, px + max(8, bar_w * stats['n'] // total), 134], 4, fill=(120, 150, 90))
    if event:
        i = index_by_id[event['agent_id']]
        name = shoppers[i]['name']
        d.ellipse([px, 152, px + 22, 174], fill=PALETTE[i % 10])
        d.text((px + 32, 150), name, font=font(18, True), fill=INK)
        action = event['action'] or {}
        step = action.get('step') or 'invalid reply'
        colour = BAD if event['outcome'] != 'applied' else (IMPULSE if stats['flash'] else INK)
        label = step.replace('_', ' ')
        if step == 'grab':
            label = 'grab ' + (stats['product'] or '')
            if stats['flash']:
                label += '   (impulse: not on list)'
        d.text((px, 188), label, font=font(17, True), fill=colour)
        if event['outcome'] != 'applied':
            d.text((px, 214), f"rejected: {event['failure']}", font=font(14), fill=BAD)
        reason = action.get('reason', '')
        y = 242
        words, line = reason.split(), ''
        for word in words:
            if d.textlength(line + ' ' + word, font=font(14)) > bar_w:
                d.text((px, y), line, font=font(14), fill=MUTED)
                y, line = y + 20, word
            else:
                line = (line + ' ' + word).strip()
        if line and y < 330:
            d.text((px, y), line, font=font(14), fill=MUTED)
    top = 350
    for label, value in [('Checked out', f"{stats['finished']} / {len(shoppers)}"), ('Items grabbed', stats['grabs']),
                         ('Impulse grabs', stats['impulse']), ('Rejected actions', stats['rejected'])]:
        d.text((px, top), label, font=font(14), fill=MUTED)
        d.text((px + bar_w, top), str(value), font=font(18, True), fill=IMPULSE if label == 'Impulse grabs' else INK, anchor='ra')
        top += 34
    d.text((px, top + 14), 'Shoppers', font=font(14, True), fill=INK)
    for i, shopper in enumerate(shoppers):
        pos = positions[shopper['id']]
        row = top + 40 + (i % 5) * 26
        col = px + (i // 5) * (bar_w // 2)
        d.ellipse([col, row, col + 14, row + 14], fill=PALETTE[i % 10])
        suffix = ' ✓' if pos['phase'] == 'FinishedState' else f" · {len(pos['cart'])}"
        d.text((col + 22, row - 2), shopper['name'].split()[0] + suffix, font=font(14), fill=INK)
    d.text((24, H - 24), 'Drawn only from the recorded run; playback cannot change outcomes.', font=font(12), fill=MUTED)
    return image


def card(lines, run):
    image = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(image)
    y = 200
    for text, size, bold, colour in lines:
        d.text((W // 2, y), text, font=font(size, bold), fill=colour, anchor='mm')
        y += size + 22
    return image


def render(run_path, out_path, fps=20):
    run = load(run_path)
    shoppers, events = run['shoppers'], run['events']
    index_by_id = {s['id']: i for i, s in enumerate(shoppers)}
    wanted = {s['id']: {i['product_id'] for i in s['list']} for s in shoppers}
    names = {p['id']: p['name'] for p in run['catalogue']}
    positions = {k: dict(v) for k, v in run['initial']['states'].items()}
    trail = {k: [(v['x'], v['y'])] for k, v in positions.items()}
    summary = run['summary']
    intro = card([("Simply", 54, True, INK), (f"{run['layout']['id'].replace('_', ' ')} · {run['source']['model']}", 28, False, INK),
                  (f"{len(shoppers)} shoppers · {len(events)} recorded decisions · guided_nav_v3", 20, False, MUTED)], run)
    outro = card([("Result", 44, True, INK),
                  (f"{summary['finished_count']} of {summary['shopper_count']} shoppers checked out", 28, False, INK),
                  (f"List items bought: {summary['purchased_unit_fulfillment']:.1%}", 24, False, INK),
                  (f"Invalid replies: {summary['failures']['invalid_decision']} · rejected moves: {summary['failures']['grid_rejected']}", 20, False, MUTED),
                  ("Single recorded run, 10 shoppers: descriptive only.", 16, False, MUTED)], run)
    stats = {'n': 0, 'finished': 0, 'grabs': 0, 'impulse': 0, 'rejected': 0, 'flash': False, 'product': ''}
    with tempfile.TemporaryDirectory() as tmp:
        count = 0

        def save(image, times=1):
            nonlocal count
            for _ in range(times):
                image.save(f'{tmp}/f{count:06d}.png')
                count += 1
        save(intro, fps * 2)
        for event in events:
            stats['n'] += 1
            action = event['action'] or {}
            stats['flash'] = False
            stats['product'] = ''
            if event['outcome'] != 'applied':
                stats['rejected'] += 1
            if action.get('step') == 'grab' and event['outcome'] == 'applied':
                stats['grabs'] += 1
                stats['product'] = names.get(action['product_id'], action['product_id'])
                if action['product_id'] not in wanted[event['agent_id']]:
                    stats['impulse'] += 1
                    stats['flash'] = True
            before = positions[event['agent_id']]['phase']
            positions[event['agent_id']] = dict(event['after'])
            if before != 'FinishedState' and event['after']['phase'] == 'FinishedState':
                stats['finished'] += 1
            trail[event['agent_id']].append((event['after']['x'], event['after']['y']))
            save(frame(run, shoppers, positions, trail, event, stats, index_by_id, len(events)))
        save(outro, fps * 4)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', f'{tmp}/f%06d.png',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(out_path)], check=True)
    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('out')
    parser.add_argument('--fps', type=int, default=20)
    args = parser.parse_args()
    print(render(args.run, args.out, args.fps))
