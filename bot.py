import os
import io
import logging
import math
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageSequence
import telebot
from telebot import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
bot = telebot.TeleBot(BOT_TOKEN)

user_sessions = {}

# ---- Animation effects ----
EFFECTS = {
    "Fade In/Out": {
        "desc": "Smooth fade in then out",
        "frames": 20,
        "fps": 15,
    },
    "Zoom In": {
        "desc": "Slow zoom into the image",
        "frames": 20,
        "fps": 15,
    },
    "Zoom Out": {
        "desc": "Zoom out from close-up",
        "frames": 20,
        "fps": 15,
    },
    "Slide Left": {
        "desc": "Slide image from right to left",
        "frames": 20,
        "fps": 18,
    },
    "Slide Up": {
        "desc": "Slide image upward",
        "frames": 20,
        "fps": 18,
    },
    "Bounce": {
        "desc": "Gentle bounce up and down",
        "frames": 24,
        "fps": 18,
    },
    "Rotate": {
        "desc": "Slow full rotation",
        "frames": 30,
        "fps": 20,
    },
    "Pulse": {
        "desc": "Rhythmic scale pulse",
        "frames": 24,
        "fps": 18,
    },
    "Glitch": {
        "desc": "RGB channel glitch effect",
        "frames": 16,
        "fps": 12,
    },
    "Ken Burns": {
        "desc": "Cinematic pan and zoom",
        "frames": 30,
        "fps": 20,
    },
}

SPEEDS = {
    "Slow":   0.5,
    "Normal": 1.0,
    "Fast":   2.0,
}

SIZES = {
    "Small  (320px)": 320,
    "Medium (480px)": 480,
    "Large  (640px)": 640,
}

MAX_GIF_SIDE = 640


def resize_for_gif(img, max_side):
    w, h = img.size
    scale = min(max_side / w, max_side / h, 1.0)
    nw, nh = int(w * scale), int(h * scale)
    # Make even dimensions
    nw = nw if nw % 2 == 0 else nw - 1
    nh = nh if nh % 2 == 0 else nh - 1
    return img.resize((nw, nh), Image.LANCZOS)


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def make_fade(img, n_frames):
    frames = []
    w, h = img.size
    for i in range(n_frames):
        t = i / (n_frames - 1)
        # Triangle: fade in first half, fade out second half
        alpha = 1.0 - abs(t * 2 - 1)
        alpha = ease_in_out(alpha)
        frame = img.copy().convert("RGBA")
        black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        blended = Image.blend(black, frame, alpha)
        frames.append(blended.convert("RGB"))
    return frames


def make_zoom_in(img, n_frames):
    frames = []
    w, h = img.size
    for i in range(n_frames):
        t = ease_in_out(i / (n_frames - 1))
        scale = 1.0 + t * 0.35
        nw, nh = int(w * scale), int(h * scale)
        zoomed = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        frame = zoomed.crop((left, top, left + w, top + h))
        frames.append(frame.convert("RGB"))
    return frames


def make_zoom_out(img, n_frames):
    frames = []
    w, h = img.size
    for i in range(n_frames):
        t = ease_in_out(i / (n_frames - 1))
        scale = 1.35 - t * 0.35
        nw, nh = int(w * scale), int(h * scale)
        zoomed = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        frame = zoomed.crop((left, top, left + w, top + h))
        frames.append(frame.convert("RGB"))
    return frames


def make_slide_left(img, n_frames):
    frames = []
    w, h = img.size
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    for i in range(n_frames):
        t = ease_in_out(i / (n_frames - 1))
        offset = int(w * (1.0 - t))
        frame = bg.copy()
        frame.paste(img, (-offset, 0))
        frames.append(frame)
    return frames


def make_slide_up(img, n_frames):
    frames = []
    w, h = img.size
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    for i in range(n_frames):
        t = ease_in_out(i / (n_frames - 1))
        offset = int(h * (1.0 - t))
        frame = bg.copy()
        frame.paste(img, (0, -offset))
        frames.append(frame)
    return frames


def make_bounce(img, n_frames):
    frames = []
    w, h = img.size
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    amp = int(h * 0.06)
    for i in range(n_frames):
        t = i / n_frames
        offset = int(math.sin(t * math.pi * 2) * amp)
        frame = bg.copy()
        frame.paste(img, (0, offset))
        frames.append(frame)
    return frames


def make_rotate(img, n_frames):
    frames = []
    w, h = img.size
    bg_color = (0, 0, 0)
    for i in range(n_frames):
        angle = 360 * i / n_frames
        rotated = img.convert("RGBA").rotate(angle, resample=Image.BICUBIC, expand=False)
        bg = Image.new("RGBA", (w, h), bg_color + (255,))
        bg.paste(rotated, (0, 0), rotated)
        frames.append(bg.convert("RGB"))
    return frames


def make_pulse(img, n_frames):
    frames = []
    w, h = img.size
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    for i in range(n_frames):
        t = i / n_frames
        scale = 1.0 + math.sin(t * math.pi * 2) * 0.08
        nw, nh = int(w * scale), int(h * scale)
        scaled = img.resize((nw, nh), Image.LANCZOS)
        frame = bg.copy()
        ox = (w - nw) // 2
        oy = (h - nh) // 2
        frame.paste(scaled, (ox, oy))
        frames.append(frame)
    return frames


def make_glitch(img, n_frames):
    frames = []
    w, h = img.size
    r, g, b = img.convert("RGB").split()
    for i in range(n_frames):
        shift = int(math.sin(i / n_frames * math.pi * 4) * 8)
        r_shifted = ImageSequence.Iterator  # placeholder
        frame = img.copy().convert("RGB")
        r2 = r.transform((w, h), Image.AFFINE, (1, 0, shift, 0, 1, 0))
        b2 = b.transform((w, h), Image.AFFINE, (1, 0, -shift, 0, 1, 0))
        merged = Image.merge("RGB", (r2, g, b2))
        # Random horizontal scan glitch
        if i % 3 == 0:
            draw = ImageDraw.Draw(merged)
            for _ in range(random.randint(1, 4)):
                import random as _r
                gy = _r.randint(0, h - 1)
                gw = _r.randint(10, w // 3)
                gx = _r.randint(0, w - gw)
                strip = img.crop((gx, gy, gx + gw, gy + 2))
                merged.paste(strip, (gx + _r.randint(-10, 10), gy))
        frames.append(merged)
    return frames


def make_ken_burns(img, n_frames):
    frames = []
    w, h = img.size
    # Pan from top-left zoom to bottom-right
    for i in range(n_frames):
        t = ease_in_out(i / (n_frames - 1))
        scale = 1.3 - t * 0.15
        nw, nh = int(w * scale), int(h * scale)
        zoomed = img.resize((nw, nh), Image.LANCZOS)
        ox = int((nw - w) * t * 0.6)
        oy = int((nh - h) * t * 0.6)
        ox = max(0, min(ox, nw - w))
        oy = max(0, min(oy, nh - h))
        frame = zoomed.crop((ox, oy, ox + w, oy + h))
        frames.append(frame.convert("RGB"))
    return frames


RENDERERS = {
    "Fade In/Out": make_fade,
    "Zoom In":     make_zoom_in,
    "Zoom Out":    make_zoom_out,
    "Slide Left":  make_slide_left,
    "Slide Up":    make_slide_up,
    "Bounce":      make_bounce,
    "Rotate":      make_rotate,
    "Pulse":       make_pulse,
    "Glitch":      make_glitch,
    "Ken Burns":   make_ken_burns,
}


def make_gif(img_bytes, effect, speed_name, max_side):
    import random
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = resize_for_gif(img, max_side)

    cfg = EFFECTS[effect]
    n_frames = cfg["frames"]
    base_fps = cfg["fps"]
    speed_mult = SPEEDS[speed_name]
    fps = base_fps * speed_mult
    duration_ms = int(1000 / fps)

    renderer = RENDERERS[effect]

    # Patch random into glitch scope
    if effect == "Glitch":
        import random as _rand
        import builtins
        builtins.random = _rand

    frames = renderer(img, n_frames)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    out.seek(0)
    return out.read()


# ---- Bot flow ----

def send_effect_picker(cid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(name, callback_data=f"effect:{name}")
        for name in EFFECTS
    ]
    markup.add(*buttons)
    bot.send_message(
        cid,
        "✨ *Step 2 — Choose an animation effect:*",
        parse_mode="Markdown",
        reply_markup=markup,
    )


def send_speed_picker(cid):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("🐢 Slow", callback_data="speed:Slow"),
        types.InlineKeyboardButton("▶️ Normal", callback_data="speed:Normal"),
        types.InlineKeyboardButton("⚡ Fast", callback_data="speed:Fast"),
    )
    bot.send_message(
        cid,
        "🕐 *Step 3 — Choose animation speed:*",
        parse_mode="Markdown",
        reply_markup=markup,
    )


def send_size_picker(cid):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("📱 Small (320px)", callback_data="size:Small  (320px)"),
        types.InlineKeyboardButton("🖥 Medium (480px)", callback_data="size:Medium (480px)"),
        types.InlineKeyboardButton("🖼 Large (640px)", callback_data="size:Large  (640px)"),
    )
    bot.send_message(
        cid,
        "📏 *Step 4 — Choose output size:*",
        parse_mode="Markdown",
        reply_markup=markup,
    )


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    cid = message.chat.id
    bot.send_message(
        cid,
        "👋 *GIF Maker Bot*\n\n"
        "Turn any image into an animated GIF!\n\n"
        "🎞 10 animation effects\n"
        "🎛 3 speed options\n"
        "📏 3 output sizes\n\n"
        "Send /make to start!",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["make"])
def cmd_make(message):
    cid = message.chat.id
    user_sessions[cid] = {"step": "photo"}
    bot.send_message(
        cid,
        "📸 *Step 1 — Send your image:*\n_(send as a photo or file)_",
        parse_mode="Markdown",
    )


@bot.message_handler(
    content_types=["photo", "document"],
    func=lambda m: user_sessions.get(m.chat.id, {}).get("step") == "photo",
)
def handle_photo(message):
    cid = message.chat.id
    session = user_sessions.get(cid, {})
    try:
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
        else:
            if not message.document.mime_type.startswith("image/"):
                bot.send_message(cid, "⚠️ Please send an image file.")
                return
            file_id = message.document.file_id

        file_info = bot.get_file(file_id)
        img_bytes = bot.download_file(file_info.file_path)
        session["img_bytes"] = img_bytes
        session["step"] = "effect"
        bot.send_message(cid, "✅ Image received!")
        send_effect_picker(cid)

    except Exception as e:
        logger.exception("Photo error")
        bot.send_message(cid, f"❌ Error: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("effect:"))
def handle_effect(call):
    cid = call.message.chat.id
    effect = call.data.split(":", 1)[1]
    session = user_sessions.setdefault(cid, {})
    session["effect"] = effect
    session["step"] = "speed"
    bot.answer_callback_query(call.id, f"{effect} selected!")
    bot.edit_message_text(
        f"✅ Effect: *{effect}*\n_{EFFECTS[effect]['desc']}_",
        cid,
        call.message.message_id,
        parse_mode="Markdown",
    )
    send_speed_picker(cid)


@bot.callback_query_handler(func=lambda call: call.data.startswith("speed:"))
def handle_speed(call):
    cid = call.message.chat.id
    speed = call.data.split(":")[1]
    session = user_sessions.setdefault(cid, {})
    session["speed"] = speed
    session["step"] = "size"
    bot.answer_callback_query(call.id, f"{speed} speed selected!")
    bot.edit_message_text(
        f"✅ Speed: *{speed}*",
        cid,
        call.message.message_id,
        parse_mode="Markdown",
    )
    send_size_picker(cid)


@bot.callback_query_handler(func=lambda call: call.data.startswith("size:"))
def handle_size(call):
    cid = call.message.chat.id
    size_key = call.data.split(":", 1)[1]
    session = user_sessions.setdefault(cid, {})
    session["size_key"] = size_key
    session["step"] = "done"
    bot.answer_callback_query(call.id, "Size selected!")
    bot.edit_message_text(
        f"✅ Size: *{size_key.strip()}*",
        cid,
        call.message.message_id,
        parse_mode="Markdown",
    )
    generate_gif(cid)


def generate_gif(cid):
    session = user_sessions.get(cid, {})
    img_bytes = session.get("img_bytes")
    effect = session.get("effect", "Fade In/Out")
    speed = session.get("speed", "Normal")
    size_key = session.get("size_key", "Medium (480px)")
    max_side = SIZES.get(size_key.strip(), 480)

    msg = bot.send_message(cid, "⏳ Rendering your GIF… this may take a few seconds.")
    try:
        result = make_gif(img_bytes, effect, speed, max_side)
        size_kb = len(result) // 1024
        bot.send_animation(
            cid,
            result,
            caption=(
                f"🎞 *Your GIF is ready!*\n"
                f"Effect: {effect} · Speed: {speed} · Size: ~{size_kb}KB\n\n"
                f"Send /make to create another!"
            ),
            parse_mode="Markdown",
        )
        bot.delete_message(cid, msg.message_id)
    except Exception as e:
        logger.exception("GIF generation error")
        bot.send_message(cid, f"❌ Failed to generate GIF: {e}")


@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    cid = message.chat.id
    user_sessions.pop(cid, None)
    bot.send_message(cid, "❌ Cancelled. Send /make to start over.")


if __name__ == "__main__":
    logger.info("GIF maker bot starting…")
    bot.infinity_polling()
