"""Back-compat shim: convert a pipeline ``ShotList`` into a timeline ``Project``.

Keeps the existing writer/pipeline working — its ShotList output imports cleanly
into the new store as a video track of clips, so nothing downstream breaks while
the agent layer is built on top.
"""

from __future__ import annotations

from flow.schemas import ShotList
from flow.store.frames import DEFAULT_FPS
from flow.store.models import Clip
from flow.store.project import Project


def import_shotlist(shotlist: ShotList, fps: int = DEFAULT_FPS) -> Project:
    """Build a Project whose video track is the shot list's scenes (in order)."""
    project = Project(title=shotlist.title, fps=fps, characters=dict(shotlist.characters))
    for order, scene in enumerate(sorted(shotlist.scenes, key=lambda s: s.id)):
        frames = scene.duration * fps
        project.clips.append(
            Clip(
                order_index=order,
                visual_prompt=scene.visual_prompt,
                characters=list(scene.characters),
                narration_segment=scene.narration_segment,
                source_duration_frames=frames,
                in_frame=0,
                out_frame=frames,
            )
        )
    return project
