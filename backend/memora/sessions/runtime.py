"""Identity of the running process.

The hackathon gate asks for recall "in a genuinely fresh session". A session
id chosen by the client proves nothing -- a browser can mint a new one without
anything having restarted, which is the wrapper failure the rules call out.

BOOT_ID is generated once, at import, and therefore exactly once per Python
process. A session records the boot that created it, so "this recall crossed a
process restart" becomes a fact a judge can check rather than a claim the demo
makes: if the prior session's boot_id differs from the current one, the process
that wrote it is gone, and everything recalled came from Sibyl rather than from
anything still resident in memory.
"""

import os
import time
import uuid

BOOT_ID: str = uuid.uuid4().hex[:12]
BOOT_PID: int = os.getpid()
BOOT_AT: float = time.time()


def boot_info() -> dict:
    """What identifies this process run, for storage and for display."""
    return {"boot_id": BOOT_ID, "pid": BOOT_PID, "booted_at": BOOT_AT}
