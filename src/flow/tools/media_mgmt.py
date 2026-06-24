"""Media-management tools — folders + library asset organization (pure store).

Folder/media ops are decoupled from clips (a clip references source_media_id),
so reorganizing or renaming never breaks a render. Deletes are soft (Trash) and
reference-aware. All mutating; dispatch records undo + persists.
"""

from __future__ import annotations

from src.flow.store.media import Folder
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool


@tool("create_folder", "Create a media-library folder (optionally nested).",
      {"project_id": "string?", "name": "string",
       "parent_folder_id": {"type": "string", "optional": True}},
      mutating=True)
def create_folder(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    parent = args.get("parent_folder_id")
    if parent and not any(f.folder_id == parent for f in p.folders):
        return result.error("not_found", f"no folder {parent}")
    folder = Folder(name=args["name"], parent_folder_id=parent)
    p.folders.append(folder)
    return result.ok(summary=f"created folder {folder.name}", folder_id=folder.folder_id)


@tool("move_to_folder", "Move media assets into a folder (or to root with null).",
      {"project_id": "string?",
       "media_ids": {"type": "array", "items": "string"},
       "folder_id": {"type": "string", "optional": True,
                     "description": "target folder; omit/null for root"}},
      mutating=True)
def move_to_folder(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    target = args.get("folder_id")
    if target and not any(f.folder_id == target for f in p.folders):
        return result.error("not_found", f"no folder {target}")
    moved = 0
    for mid in args["media_ids"]:
        asset = p.get_media(mid)
        if asset and not asset.trashed:
            asset.folder_id = target
            moved += 1
    return result.ok(summary=f"moved {moved} assets")


@tool("rename_media", "Rename a library asset (display filename; ref-safe).",
      {"project_id": "string?", "media_id": "string", "name": "string"},
      mutating=True)
def rename_media(ctx: ToolContext, args: dict) -> dict:
    asset = ctx.project.get_media(args["media_id"])
    if asset is None:
        return result.error("not_found", f"no media {args['media_id']}")
    asset.filename = args["name"]
    return result.ok(summary=f"renamed media to {args['name']}")


@tool("rename_folder", "Rename a folder.",
      {"project_id": "string?", "folder_id": "string", "name": "string"},
      mutating=True)
def rename_folder(ctx: ToolContext, args: dict) -> dict:
    folder = next((f for f in ctx.project.folders if f.folder_id == args["folder_id"]), None)
    if folder is None:
        return result.error("not_found", f"no folder {args['folder_id']}")
    if folder.system:
        return result.error("protected", "system folders cannot be renamed")
    folder.name = args["name"]
    return result.ok(summary=f"renamed folder to {args['name']}")


@tool("delete_media", "Soft-delete a library asset (moves to Trash). Blocked if a "
      "clip still references it unless force=true (which detaches references).",
      {"project_id": "string?", "media_id": "string",
       "force": {"type": "boolean", "optional": True}},
      mutating=True)
def delete_media(ctx: ToolContext, args: dict) -> dict:
    asset = ctx.project.get_media(args["media_id"])
    if asset is None:
        return result.error("not_found", f"no media {args['media_id']}")
    if asset.used_by and not args.get("force"):
        return result.error(
            "in_use", f"asset is referenced by {len(asset.used_by)} clip(s)",
            hint="pass force=true to detach and trash")
    if args.get("force"):
        for clip in ctx.project.clips:
            if clip.source_media_id == asset.media_id:
                clip.source_media_id = None
        asset.used_by = []
    asset.trashed = True
    return result.ok(summary=f"trashed media {asset.media_id}")


@tool("delete_folder", "Delete a folder. 'contents' policy: require_empty (default), "
      "move_up (re-parent children), or trash_all (soft-delete contained assets).",
      {"project_id": "string?", "folder_id": "string",
       "contents": {"type": "string", "enum": ["require_empty", "move_up", "trash_all"],
                    "optional": True, "default": "require_empty"}},
      mutating=True)
def delete_folder(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    fid = args["folder_id"]
    folder = next((f for f in p.folders if f.folder_id == fid), None)
    if folder is None:
        return result.error("not_found", f"no folder {fid}")
    if folder.system:
        return result.error("protected", "system folders cannot be deleted")
    policy = args.get("contents", "require_empty")
    children = [f for f in p.folders if f.parent_folder_id == fid]
    assets = [m for m in p.media if m.folder_id == fid and not m.trashed]
    if policy == "require_empty" and (children or assets):
        return result.error("not_empty", "folder has contents",
                            hint="use contents=move_up or trash_all")
    if policy == "move_up":
        for f in children:
            f.parent_folder_id = folder.parent_folder_id
        for m in assets:
            m.folder_id = folder.parent_folder_id
    elif policy == "trash_all":
        for m in assets:
            m.trashed = True
        for f in children:
            f.parent_folder_id = folder.parent_folder_id
    p.folders = [f for f in p.folders if f.folder_id != fid]
    return result.ok(summary=f"deleted folder {fid}")
