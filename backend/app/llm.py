import time

import app.extract as ex


def chat_json(system, user, max_tokens=1500):
    """Ask the model for JSON. Returns (data, stats)."""
    client = ex.get_client()
    started = time.time()
    reply = None
    for attempt in range(3):  # try up to 3 times if the service is busy
        try:
            reply = client.chat.completions.create(
                model=ex.MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

    seconds = time.time() - started
    usage = getattr(reply, "usage", None)
    tokens = getattr(usage, "completion_tokens", None) if usage else None
    data = ex.clean_json(reply.choices[0].message.content)
    return data, {"ms": int(seconds * 1000), "completion_tokens": tokens}