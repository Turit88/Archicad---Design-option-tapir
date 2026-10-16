# Design Options for Archicad (Tapir) | Idea: Tamás Túri | Coding with Claude Opus 5.5 (Anthropic) | 2026-10-15
# License: free to use and modify, provided the original author (Tamás Túri) is credited.
import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import tkinter as tk
import urllib.request
from collections import Counter, defaultdict
from contextlib import contextmanager
from tkinter import font as tkfont
from tkinter import ttk

# Tapir "Run Script" passes the Archicad port as --port (standalone file: aclib is not needed)
_parser = argparse.ArgumentParser()
_parser.add_argument("--host", default="http://127.0.0.1")
_parser.add_argument("--port", type=int, default=19723)
_parser.add_argument("--detached", action="store_true")    # the independent copy started by relaunch_detached()
_args, _ = _parser.parse_known_args()
HOST, PORT, DETACHED = _args.host, _args.port, _args.detached

TITLE = "Design Options"
AUTHOR = "by Tamás Túri"            # faint, bottom right corner of the window
MIN_ARCHICAD = 29                   # design option commands exist from Archicad 29
MIN_TAPIR = (1, 7, 0)               # GetDetailsOfElements "fields"
NULL_GUID = "00000000-0000-0000-0000-000000000000"
BATCH = 200                         # elements per request
MODE_COPY, MODE_MOVE = "copy", "move"
OPENINGS = {"Window", "Door", "Skylight", "Opening"}
SUBELEMENTS = {"BeamSegment", "ColumnSegment", "Riser", "Tread", "StairStructure"}
MAX_MESSAGE_LINES = 8               # longer results are summarized
MIN_WIDTH = 300                     # minimum window width and label wrap length (px)
DECIMALS = 6                        # numbers are rounded to this when comparing elements
MAIN = ""                           # key of the main model in the matrix (design options use their GUID)
VISIBLE_ROWS = 12                   # the matrix is at most this many rows high (then it scrolls)
SELECTED, PRESENT, DELETE, ADD = "◉", "●", "✕", "+"
BASIC_FIELDS = ["type", "id", "floorIndex", "layerIndex"]
SET_BACKGROUNDS = ["#ffffff"]       # matrix background per design option set (sets are separated by thick lines)
ACTIVE_ROW_COLOR = "#ccffcc"        # selected rows (the selection green of the Archicad Design Options palette)
LINE_COLOR, THICK_LINE_COLOR = "#d4d4d4", "#6f6f6f"
MARK_COLORS = {SELECTED: "#1a1a1a", PRESENT: "#4a4a4a", DELETE: "#c62828", ADD: "#1b7f3b"}
MARK_SIZE, MARK_WIDTH = 5, 2        # half size and stroke width of the ✕ / + marks (px)
SELECTION_POLL_MS = 500             # matrix: how often the Archicad selection is read (the rows follow it)
BUSY_CODE = 4001                    # Archicad: "Invalid program status (ongoing user input)"
BUSY_WAIT = 10.0                    # seconds to keep retrying a command while Archicad is busy
ARCHICAD_WATCH_MS = 1000            # how often to check that Archicad still runs (the window closes with it)
REFRESH_ICON = (                    # refresh button icon: circle with two curved arrows, 22 px PNG, base64
    "iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAEHElEQVR42rWVy4scVRTGv3PrMdWDmcRkEXvTSgxIIFkN3Zmp1+0J"
    "hEmyEDG58QERxex8/AMq7Rh0IWSTiK5EghAfHUU3KkkIXTNV3WmGQSRBECcYmcA4aNQkkq7urrrHTbcMkwlxk7O89Z0fdb5773eB"
    "dUopZaxdk1JuklJu+j9aAKD1hPV6PZdSOnmeKyJ6hpl3AXhwIPmLiC4x8yeGYdSjKEqHPXcFDwVBEDwF4D0ABQDfaq0TAD8NZI8J"
    "ITwA+wF0mPmVOI4/XQ8+HNUEgCAIjk9NTbGUcqZSqYzhLlWpVMbCMDwmpcyCIDi+mnGHT0EQHA/DsOt5nn83q9aW67pHpZTdIXzI"
    "ouEIvu8ry7I+73a7brPZbEkpnSiK0nK5vMVxHAXAAwAhRDPP8zNxHP8eBMEJZi5prd90HOf7Xq93OI7julLKIAA0MTHhWJb1m9b6"
    "ZJIkrw+hrus+b5rm+4ZhFPr9/nUAZBjG5jzPrwL40bbtA91ut5Ukieu67jtCiJeyLHvo4sWLqQDApmkeZGYnz/O3lVJGFEWp7/tH"
    "RkdHP2LmRpqmu4rF4tY4jrfkef6sbduP2LZ9IMsyANhYq9WE1voYAMc0zYMAmADA9/1zzPx3kiQKAJXL5c2FQuEqgGR2dnbfKr95"
    "cnJyp2VZTzLzJBHt1lrf6nQ62xcWFvqe550hoo1xHO8VtVpNMPNOANGw2bbtQ6ZpPqC1fhUAxsfHLQAMgFqt1uXZ2dm35ubm9pum"
    "uQPA4W3bttGgt8HMO2u1mhCNRmOMiDYQ0SIAVkoZWZZ91el0vGKxeAUALSws9Ad/zQDE4FiJCxcurMRx3AaQA2AiWiSiDY1GY8xc"
    "7wi12+0VACsDiBFFkQagB591FEWslBJLS0sVZv4VwB9rGaJard5k5lvMvH0wjuH7/u49e/ZsHUCyAZRW27K8vPzo6Oho2zTNJwY3"
    "jph5OzPfqlarN1dv3o0kSQ6Nj49bhUJhUQixgZnbRNTq9/tftlqty8M9AIAwDL8D4Hc6nYfn5+f/BMCe59WJaFMcx3uHVpwiog8n"
    "JiYK09PT3fPnz/8DoGRZ1j4A+7TWPwO4rJQS165d22Ga5ru2bU+nafrc/Pz8daWUsbS0ZBPR4wBeBAABgLIs+wJAKoR4Y2ZmRgO4"
    "YZomer3eN71e76phGKd937++vLy84jjOJSKq3r59+4U4jj+WUjr1ej03DOM1IkoHLDKUUsbZs2d7pVLpysjIyIlisfi1EKKstT4X"
    "x/GRUql0WgjxC4CUiBa11h+kaXq03W63Vt3QyZGRkVN5nh9pNps//JfRq0NIStl1Xfco7l0EAJ7n+WEY3hFC68amlDILw/DYvWJT"
    "SjkzNTXF68XmukHv+/7TRHTy/wQ9gJfn5uY+Wxv09+1pwv16TP8FHccgifKdJrwAAAAASUVORK5CYII=")


# ---------------------------------------------------------------- Archicad
class ArchicadError(Exception):
    pass


def send_command(command, parameters=None, timeout=600, wait=BUSY_WAIT):
    """One Archicad JSON command. While Archicad is waiting for user input (4001 "ongoing user input": e.g. a tool
    is half-way, or the user is clicking), the command is retried for at most `wait` seconds."""
    body = {"command": command}
    if parameters is not None:
        body["parameters"] = parameters
    deadline = time.monotonic() + wait
    while True:
        req = urllib.request.Request(f"{HOST}:{PORT}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                answer = json.loads(resp.read().decode("utf-8"))
        except OSError as e:
            raise ArchicadError(f"Archicad not reachable on port {PORT}.") from e
        if answer.get("succeeded", False):
            return answer.get("result", {})
        error = answer.get("error") or {}
        if error.get("code") != BUSY_CODE:
            raise ArchicadError(f"{command}: {error}")
        if time.monotonic() >= deadline:
            raise ArchicadError("Archicad is busy (an input is in progress). Finish or cancel it in Archicad "
                                "(e.g. Esc), then try again.")
        time.sleep(0.3)


def tapir(name, params=None, timeout=600, wait=BUSY_WAIT):
    request = {"addOnCommandId": {"commandNamespace": "TapirCommand", "commandName": name}}
    if params is not None:
        request["addOnCommandParameters"] = params
    resp = send_command("API.ExecuteAddOnCommand", request, timeout, wait).get("addOnCommandResponse", {})
    if isinstance(resp, dict) and "error" in resp and len(resp) == 1:
        raise ArchicadError(f"{name}: {resp['error']}")
    return resp


def chunks(items, n=BATCH):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def version_tuple(text):
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:3])


def element_id(guid):
    return {"elementId": {"guid": guid}}


def describe_types(types):
    """Counter({"Wall": 3, "Window": 2}) -> "3 Wall, 2 Window" """
    return ", ".join(f"{n} {t}" for t, n in types.most_common())


def is_dependent(element_type):
    """Follows its host (opening, subelement): relinking the host moves it too; relinking it alone fails."""
    return (element_type in OPENINGS or element_type in SUBELEMENTS
            or (element_type.startswith("Railing") and element_type != "Railing")
            or (element_type.startswith("CurtainWall") and element_type != "CurtainWall"))


def connect():
    """Project info; ArchicadError if Archicad / Tapir is not suitable."""
    ac = send_command("API.GetProductInfo").get("version", 0)
    if ac < MIN_ARCHICAD:
        raise ArchicadError(f"Archicad {ac}: design options need Archicad {MIN_ARCHICAD}+.")
    tv = tapir("GetAddOnVersion").get("version", "")
    if version_tuple(tv) < MIN_TAPIR:
        raise ArchicadError(f"Tapir {tv} is too old, {'.'.join(map(str, MIN_TAPIR))}+ needed.")
    info = tapir("GetProjectInfo")
    info["archicad"], info["tapir"] = ac, tv
    return info


def design_option_sets():
    """The design option sets in their own order: [{"name", "options": [{"guid", "id", "name", "set"}]}]"""
    details = {o["designOptionId"]["guid"].upper(): o for o in tapir("GetDesignOptions").get("designOptions", [])}
    result = []
    for s in tapir("GetDesignOptionSets").get("designOptionSets", []):
        options = []
        for o in s.get("designOptions", []):
            g = o["designOptionId"]["guid"].upper()
            d = details.get(g, {})
            options.append({"guid": g, "id": d.get("id", ""), "name": d.get("name", ""), "set": s.get("name", "")})
        result.append({"name": s.get("name", ""), "options": options})
    return result


def option_label(o):
    return f"{o['id'] + ' ' if o['id'] else ''}{o['name']}"


def design_options_of(guids):
    """{element GUID: design option GUID, or None (main model)}"""
    result = {}
    for part in chunks(guids):
        for r in tapir("GetDesignOptionForElements", {"elements": [element_id(g) for g in part]}).get("designOptionForElements", []):
            o = r.get("designOption") if r.get("type") == "LinkedToDesignOption" else None
            result[r["elementId"]["guid"].upper()] = o["designOptionId"]["guid"].upper() if o else None
    return result


def elements_of_options(option_guids):
    """{element GUID: design option GUID} - every element of the design options, hidden ones too."""
    result = {}
    if not option_guids:
        return result
    answer = tapir("GetElementsOfDesignOptions", {"designOptions": [{"designOptionId": {"guid": g}} for g in option_guids]})
    for x in answer.get("elementsOfDesignOptions", []):
        o = (x.get("designOptionId") or {}).get("guid", "").upper()
        for e in x.get("elements", []):
            result[e["elementId"]["guid"].upper()] = o
    return result


def details_of(guids, fields):
    """{element GUID: GetDetailsOfElements record} - only the requested fields."""
    result = {}
    for part in chunks(guids):
        answer = tapir("GetDetailsOfElements", {"elements": [element_id(g) for g in part], "fields": fields})
        result.update(zip(part, answer.get("detailsOfElements", [])))
    return result


def owner_of(record):
    """GUID of the host element from a GetDetailsOfElements record (wall of an opening, window of a marker), or None."""
    g = (((record.get("details") or {}).get("ownerElementId") or {}).get("guid") or "").upper()
    return g if g and g != NULL_GUID else None


def editable_elements(guids):
    """GUIDs of the elements editable right now (not on a hidden / locked layer, not a hotlink instance, not locked)."""
    result = set()
    for part in chunks(guids):
        answer = tapir("FilterElements", {"elements": [element_id(g) for g in part], "filters": ["IsEditable"]})
        result |= {e["elementId"]["guid"].upper() for e in answer.get("elements", [])}
    return result


def selected_guids(timeout=600, wait=BUSY_WAIT):
    return [e["elementId"]["guid"].upper()
            for e in tapir("GetSelectedElements", timeout=timeout, wait=wait).get("elements", [])]


def read_selection():
    """The selected elements: [{"guid", "type", "option" (GUID / None), "editable", "owner" (GUID / None)}].
    editable: editable, or can be made editable (hidden / locked layer, manual lock - see unlocked());
    only a hotlink instance is not."""
    guids = selected_guids()
    if not guids:
        return []
    data = details_of(guids, ["type", "details", "hotlinkId"])
    options = design_options_of(guids)
    return [{"guid": g, "type": data.get(g, {}).get("type", "?"), "option": options.get(g),
             "editable": not data.get(g, {}).get("hotlinkId"), "owner": owner_of(data.get(g, {}))} for g in guids]


# ---------------------------------------------------------------- layers, locking
def layer_records():
    """{layer index: GetLayers record (attributeId, name, isHidden, isLocked, ...)}"""
    ids = send_command("API.GetAttributesByType", {"attributeType": "Layer"}).get("attributeIds", [])
    result = {}
    for part in chunks(ids):
        for layer in tapir("GetLayers", {"attributeIds": part}).get("layers", []):
            if "index" in layer:
                result[layer["index"]] = layer
    return result


def set_layer_flags(records, hidden=None, locked=None):
    """Sets visibility / lock of the layers; None: as in the record (the original state). Other layer settings
    (wireframe, intersection group) are kept."""
    data = [{"attributeId": r["attributeId"], "name": r.get("name", ""),
             "isHidden": bool(r.get("isHidden")) if hidden is None else hidden,
             "isLocked": bool(r.get("isLocked")) if locked is None else locked} for r in records]
    for part in chunks(data, 100):
        tapir("CreateLayers", {"layerDataArray": part, "overwriteExisting": True})


@contextmanager
def unlocked(guids):
    """Makes the given elements editable inside the with-block: opens their hidden / locked layers and unlocks
    manually locked elements; everything is restored on exit (on error too). On such elements Archicad silently
    skips a copy and refuses a delete. Yields the set of GUIDs that still cannot be edited (hotlink instances)."""
    guids = sorted(set(guids))
    not_editable = [g for g in guids if g not in editable_elements(guids)] if guids else []
    opened_layers, unlocked_elements, remaining = [], [], set()
    try:
        if not_editable:
            data = details_of(not_editable, ["layerIndex", "hotlinkId"])
            remaining = {g for g in not_editable if data.get(g, {}).get("hotlinkId")}
            tried = [g for g in not_editable if g not in remaining]
            layers = {data[g].get("layerIndex") for g in tried}
            closed = [r for i, r in layer_records().items() if i in layers and (r.get("isHidden") or r.get("isLocked"))]
            if closed:
                opened_layers = closed
                set_layer_flags(closed, hidden=False, locked=False)
            editable = editable_elements(tried)
            still_locked = [g for g in tried if g not in editable]
            if still_locked:                # still not editable with its layer open: manual lock
                tapir("UnlockElements", {"elements": [element_id(g) for g in still_locked]})
                unlocked_elements = still_locked
                editable = editable_elements(tried)
            remaining |= {g for g in tried if g not in editable}
        yield remaining
    finally:
        # restore; if Archicad does not accept it even after waiting, report by name what was left open
        problems = []
        if unlocked_elements:
            try:
                tapir("LockElements", {"elements": [element_id(g) for g in unlocked_elements]})
            except ArchicadError:
                problems.append(f"{len(unlocked_elements)} element(s) left unlocked")
        if opened_layers:
            try:
                set_layer_flags(opened_layers)
            except ArchicadError:
                problems.append("layer(s) left open: " + ", ".join(r.get("name", "?") for r in opened_layers))
        if problems:
            raise ArchicadError("NOT RESTORED (Archicad busy): " + "; ".join(problems) + ". Please fix by hand.")


def all_elements():
    """Tapir GetAllElements: unlike the Archicad command it returns 2D elements and subelements too."""
    return {e["elementId"]["guid"].upper() for e in tapir("GetAllElements").get("elements", [])}


# ---------------------------------------------------------------- groups
def groups_suspended():
    return bool(tapir("GetSuspendGroupsMode").get("suspendGroups"))


@contextmanager
def suspended_groups():
    """Suspend Groups on inside the with-block (then an edit affects only the given elements, not their whole group);
    the previous mode is restored on exit."""
    before = groups_suspended()
    if not before:
        tapir("SetSuspendGroupsMode", {"suspendGroups": True})
    try:
        yield
    finally:
        if not before:
            tapir("SetSuspendGroupsMode", {"suspendGroups": False})


def top_groups(guids):
    """{element GUID: GUID of its top-level group, or None}. GetGroupsOfElements gives the direct group; asked for a
    group, it gives the parent group, so nested groups are walked up level by level."""
    top = {g: None for g in guids}
    current = {g: g for g in guids}         # element -> the id whose parent is asked next
    while current:
        ids = sorted(set(current.values()))
        parents = {}
        for part in chunks(ids):
            answer = tapir("GetGroupsOfElements", {"elements": [element_id(i) for i in part]}).get("groupGuids", [])
            for i, r in zip(part, answer):
                p = (r.get("groupId") or {}).get("guid")
                if p:
                    parents[i] = p.upper()
        current = {g: parents[c] for g, c in current.items() if c in parents}
        top.update(current)
    return top


def independent(guids):
    """The elements that do not follow a host (no opening, marker or subelement)."""
    data = details_of(guids, ["type", "details"])
    return [g for g in guids if not is_dependent(data.get(g, {}).get("type", "?")) and not owner_of(data.get(g, {}))]


def restore_selection(guids):
    """Copying drops the Archicad selection: the original (still existing) elements are selected again."""
    existing = all_elements()
    now = set(selected_guids())
    tapir("ChangeSelectionOfElements", {"addElementsToSelection": [element_id(g) for g in guids if g in existing and g not in now],
                                        "removeElementsFromSelection": [element_id(g) for g in now if g not in guids]})


# ---------------------------------------------------------------- copying
def plan_copy(elements, targets, mode):
    """What to do: ({target GUID: [element GUIDs to copy]}, {element GUID: target GUID} to move,
    Counter({reason: count}) skipped). The order of the targets matters (in move mode the first gets the original)."""
    selected = {e["guid"] for e in elements}
    copies = {t: [] for t in targets}
    moves, skipped = {}, Counter()
    for e in elements:
        if not e["editable"]:
            skipped["hotlink, read-only"] += 1
            continue
        if e["owner"] in selected:
            skipped["comes with its host"] += 1
            continue
        rest = [t for t in targets if t != e["option"]]
        if mode == MODE_MOVE and e["option"] not in targets and rest:
            moves[e["guid"]] = rest.pop(0)
        for t in rest:
            copies[t].append(e["guid"])
    return {t: g for t, g in copies.items() if g}, moves, skipped


def relink(pairs):
    """Relinks [(element GUID, design option GUID / None)]. Two passes: first the independent elements (their
    openings, markers and subelements follow), then whatever is still not in place (e.g. a window copied alone).
    Returns the read-back {element GUID: design option GUID}."""
    data = details_of([g for g, _ in pairs], ["type", "details"])
    first = [(g, o) for g, o in pairs if not is_dependent(data.get(g, {}).get("type", "?")) and not owner_of(data.get(g, {}))]
    for batch in (first, None):
        if batch is None:
            where = design_options_of([g for g, _ in pairs])
            batch = [(g, o) for g, o in pairs if where.get(g) != o]
        for part in chunks(batch):
            tapir("MoveElementsToDesignOptions", {"elementDesignOptionPairs": [
                {"elementId": {"guid": g}, "designOptionId": {"guid": o or NULL_GUID}} for g, o in part]})
    return design_options_of([g for g, _ in pairs])


def copy_in_place(guids):
    """Zero-vector MoveElements copy. It does not return the new elements, so they are the difference of the
    element lists. Returns (GUIDs not copied, GUIDs of the new elements incl. dependents)."""
    before = all_elements()
    answer = tapir("MoveElements", {"elementsWithMoveVectors": [
        {"elementId": {"guid": g}, "moveVector": {"x": 0, "y": 0, "z": 0}, "copy": True} for g in guids]})
    not_copied = [g for g, r in zip(guids, answer.get("executionResults", [])) if not r.get("success")]
    return not_copied, sorted(all_elements() - before)


def copy_keeping_groups(guids):
    """Copies the elements once each. Without Suspend Groups, copying one member of a group copies its whole top-level
    group (copying every member would copy the group that many times): so one member per group is copied, which keeps
    the grouping in the copy. If the group has members that were not asked for (more new elements appear than
    requested), that copy is deleted and the requested members are copied one by one with groups suspended.
    Returns (GUIDs not copied, GUIDs of the new elements incl. dependents)."""
    if groups_suspended():
        return copy_in_place(guids)
    top = top_groups(guids)
    singles = [g for g in guids if not top[g]]
    groups = defaultdict(list)
    for g in guids:
        if top[g]:
            groups[top[g]].append(g)
    not_copied, new = copy_in_place(singles) if singles else ([], [])
    for members in groups.values():
        failed, copied = copy_in_place(members[:1])
        if copied and len(independent(copied)) > len(members):         # part of the group only: no grouped copy
            with suspended_groups():
                for part in chunks(copied):
                    tapir("DeleteElements", {"elements": [element_id(g) for g in part]})
                failed, copied = copy_in_place(members)
        elif failed:
            failed = members
        not_copied += failed
        new += copied
    return not_copied, sorted(new)


def copy_to_options(copies, types, names):
    """Copies {target (design option GUID, None = main model): [element GUIDs]} into the target, then relinks the
    copies there. Returns (result lines, number of failures, GUIDs of the new elements incl. dependents)."""
    lines, failures, all_new = [], 0, []
    for target, guids in copies.items():
        not_copied, new = copy_keeping_groups(guids)
        all_new += new
        where = relink([(g, target) for g in new]) if new else {}
        misplaced = [g for g in new if where.get(g) != target]
        copied = len(guids) - len(not_copied)
        lines.append(f"{names[target]}: {copied} copied" + (f" (+{len(new) - copied} dependent)" if len(new) > copied else ""))
        if not_copied:
            lines.append(f"  Copy failed: {describe_types(Counter(types.get(g, '?') for g in not_copied))}")
        if misplaced:
            new_types = details_of(misplaced, ["type"])
            lines.append(f"  Not moved: {describe_types(Counter(new_types.get(g, {}).get('type', '?') for g in misplaced))}")
        if copied and not new:
            lines.append("  No new element appeared.")
        failures += len(not_copied) + len(misplaced)
    return lines, failures, all_new


def run_copy(targets, mode, names):
    """Copy view: copies / moves the selection into the target design options. Returns the result lines."""
    elements = read_selection()
    if not elements:
        raise ArchicadError("Nothing selected.")
    types = {e["guid"]: e["type"] for e in elements}
    copies, moves, skipped = plan_copy(elements, targets, mode)
    if not copies and not moves:
        return [f"Skipped {n} ({reason})" for reason, n in skipped.items()] + ["Nothing to do."]
    sources = {g for v in copies.values() for g in v} | set(moves)
    with unlocked(sources) as remaining:            # elements on hidden / locked layers and locked elements too
        if remaining:
            copies = {t: [g for g in v if g not in remaining] for t, v in copies.items()}
            copies = {t: v for t, v in copies.items() if v}
            moves = {g: t for g, t in moves.items() if g not in remaining}
            skipped["cannot be opened"] += len(remaining)
        lines = [f"Skipped {n} ({reason})" for reason, n in skipped.items()]
        new_lines, failures, _ = copy_to_options(copies, types, names)
        restore_selection([e["guid"] for e in elements])
        lines += new_lines
        if moves:
            where = relink(list(moves.items()))
            for target in dict.fromkeys(moves.values()):
                ok = sum(1 for g, t in moves.items() if t == target and where.get(g) == target)
                lines.append(f"{names[target]}: {ok} original moved")
            wrong = [g for g, t in moves.items() if where.get(g) != t]
            if wrong:
                lines.append(f"  Move failed: {describe_types(Counter(types.get(g, '?') for g in wrong))}")
            failures += len(wrong)
    return lines + ["Done." if not failures else f"Done, {failures} failed."]


# ---------------------------------------------------------------- identical elements
def rounded(x):
    """For comparison: numbers rounded to DECIMALS (-0 becomes 0), structure kept."""
    if isinstance(x, float):
        x = round(x, DECIMALS)
        return 0.0 if x == 0 else x
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def make_key(value):
    return json.dumps(rounded(value), sort_keys=True, ensure_ascii=False)


def gdl_keys(guids):
    """{element GUID: key of its GDL parameter values}; no entry for non-library-part elements."""
    result = {}
    for part in chunks(guids, 50):
        answer = tapir("GetGDLParametersOfElements", {"elements": [element_id(g) for g in part]}).get("gdlParametersOfElements", [])
        for g, r in zip(part, answer):
            if "parameters" in r:
                result[g] = make_key([[p.get("name"), p.get("value")] for p in r["parameters"]])
    return result


def signatures(guids, data=None):
    """{element GUID: identity key} - GetDetailsOfElements (BASIC_FIELDS + details) and the GDL parameter values.
    Not compared: properties, classification, surface overrides and whatever Tapir does not return."""
    if data is None:
        data = details_of(guids, BASIC_FIELDS + ["details"])
    gdl = gdl_keys(guids)
    return {g: (make_key(data.get(g, {})), gdl.get(g)) for g in guids}


def matching_rows(elements, option_guids):
    """The selected elements (except openings selected together with their host) with the elements exactly identical
    to them, one row each: [{"label", "type", "signature", "selected": [GUID], "source": GUID / None,
    "members": {place: [GUID]}}], where place is a design option GUID or MAIN; source is the (editable) selected
    element that is copied when adding. Candidates are filtered in steps: type + story + layer + ID, then details,
    finally GDL parameters."""
    selected = {e["guid"] for e in elements}
    elements = [e for e in elements if e["owner"] not in selected]
    if not elements:
        return []
    own = [e["guid"] for e in elements]
    place = elements_of_options(option_guids)

    # 1. cheap filter (type + story + layer + ID) on every element of the selected types, in the design options too
    cheap = {g: make_key([r.get(f) for f in BASIC_FIELDS]) for g, r in details_of(own, BASIC_FIELDS).items()}
    wanted = set(cheap.values())
    pool = set(place)
    for element_type in sorted({json.loads(k)[0] for k in wanted}):
        pool |= {e["elementId"]["guid"].upper() for e in tapir("GetElementsByType", {"elementType": element_type}).get("elements", [])}
    candidates = set(own) | {g for g, r in details_of(sorted(pool - set(own)), BASIC_FIELDS).items()
                             if make_key([r.get(f) for f in BASIC_FIELDS]) in wanted}

    # 2. details (position, geometry, settings), 3. GDL parameters
    data = details_of(sorted(candidates), BASIC_FIELDS + ["details"])
    wanted = {make_key(data.get(g, {})) for g in own}
    candidates = [g for g in candidates if make_key(data.get(g, {})) in wanted]
    signature = signatures(candidates, data)

    rows = {}
    for e in elements:
        r = data.get(e["guid"], {})
        name = r.get("id") or ((r.get("details") or {}).get("libPart") or {}).get("name") or ""
        row = rows.setdefault(signature[e["guid"]], {"label": f"{e['type']} {name}".strip(), "type": e["type"],
                                                     "signature": signature[e["guid"]], "selected": [], "source": None,
                                                     "members": defaultdict(list)})
        row["selected"].append(e["guid"])
        if row["source"] is None and e["editable"]:
            row["source"] = e["guid"]
    for g in candidates:
        if signature[g] in rows:
            rows[signature[g]]["members"][place.get(g, MAIN)].append(g)
    return list(rows.values())


def refresh_rows(rows, new):
    """After Apply, without a new search: the members of the rows with their current place; deleted ones drop out,
    the new copies go into their row by identity key (dependents - segments, openings - match no row)."""
    existing = all_elements()
    members = [[g for v in r["members"].values() for g in v if g in existing] for r in rows]
    row_of = {r["signature"]: i for i, r in enumerate(rows)}
    for g, s in signatures([g for g in new if g in existing]).items():
        if s in row_of:
            members[row_of[s]].append(g)
    where = design_options_of([g for m in members for g in m])
    for r, m in zip(rows, members):
        r["members"] = defaultdict(list)
        for g in m:
            r["members"][where.get(g) or MAIN].append(g)
        r["selected"] = [g for g in r["selected"] if g in existing]
        if r["source"] not in existing:
            r["source"] = r["selected"][0] if r["selected"] else None
    return rows


def delete_elements(places):
    """Deletes {element GUID: place (design option GUID / MAIN)}. DeleteElements does not delete an element of a
    design option that is not shown: such an element is first relinked to the main model and deleted there; if that
    fails too, it is relinked back. Groups are suspended meanwhile: otherwise deleting one member deletes its whole
    group. Returns (result lines, number of failures)."""
    editable = editable_elements(list(places))
    skipped = [g for g in places if g not in editable]
    to_delete = [g for g in places if g in editable]
    with suspended_groups():
        for part in chunks(to_delete):
            tapir("DeleteElements", {"elements": [element_id(g) for g in part]})
        existing = all_elements()
        left = [g for g in to_delete if g in existing]
        in_option = [g for g in left if places[g] != MAIN]
        if in_option:
            relink([(g, None) for g in in_option])
            for part in chunks(in_option):
                tapir("DeleteElements", {"elements": [element_id(g) for g in part]})
            existing = all_elements()
            left = [g for g in to_delete if g in existing]
            back = [(g, places[g]) for g in left if places[g] != MAIN]
            if back:
                relink(back)
    lines = [f"Deleted {len(to_delete) - len(left)}"]
    if skipped:
        lines.append(f"  Skipped {len(skipped)} (read-only)")
    if left:
        lines.append(f"  Delete failed: {len(left)}")
    return lines, len(skipped) + len(left)


def apply_matrix(additions, deletions, types, names):
    """Matrix view: first the additions ({target: [source GUIDs]}), then the deletions ({element GUID: place}).
    Returns (result lines, GUIDs of the new elements)."""
    lines, failures, new = [], 0, []
    selection = selected_guids()
    sources = {g for v in additions.values() for g in v} | set(deletions)
    with unlocked(sources) as remaining:            # elements on hidden / locked layers and locked elements too
        if remaining:
            additions = {t: [g for g in v if g not in remaining] for t, v in additions.items()}
            additions = {t: v for t, v in additions.items() if v}
            deletions = {g: p for g, p in deletions.items() if g not in remaining}
            lines.append(f"Skipped {len(remaining)} (hotlink, read-only)")
        if additions:
            new_lines, failures, new = copy_to_options(additions, types, names)
            lines += new_lines
        if deletions:
            new_lines, new_failures = delete_elements(deletions)
            lines += new_lines
            failures += new_failures
        restore_selection(selection)
    return lines + ["Done." if not failures else f"Done, {failures} failed."], new


# ---------------------------------------------------------------- on top of Archicad only
def archicad_process_id():
    """Process id of the Archicad listening on the Tapir port (netstat), or None."""
    try:
        output = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.decode("ascii", "ignore").splitlines():
        r = line.split()            # TCP  127.0.0.1:19723  0.0.0.0:0  LISTENING (in the Windows language)  PID
        if len(r) >= 5 and r[0] == "TCP" and r[1].endswith(f":{PORT}") and r[2] in ("0.0.0.0:0", "[::]:0"):
            return int(r[4]) if r[4].isdigit() else None
    return None


def relaunch_detached():
    """Starts an independent copy of this script and reports whether it started. Why: Tapir watches the script it
    started from a thread of its own, and on Archicad quit it neither stops the script nor that thread - the
    add-on is unloaded under the running thread and Archicad crashes. If the script started by Tapir exits at once,
    Tapir's thread ends; the independent copy is not watched by Tapir and closes itself when Archicad quits."""
    command = [sys.executable, os.path.abspath(__file__), "--host", HOST, "--port", str(PORT), "--detached"]
    flags = 0x00000008 | 0x00000200         # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    for breakaway in (0x01000000, 0):       # CREATE_BREAKAWAY_FROM_JOB: out of the job of uv, if the job allows it
        try:
            subprocess.Popen(command, creationflags=flags | breakaway, close_fds=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False


def process_alive(pid):
    """Windows: is the process still running."""
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    h = kernel32.OpenProcess(0x00100000, False, pid)           # SYNCHRONIZE
    if not h:
        return False
    try:
        return kernel32.WaitForSingleObject(wintypes.HANDLE(h), 0) == 0x102     # WAIT_TIMEOUT: not signaled yet
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(h))


_instance_mutex = None


def first_instance():
    """Windows: only one window per Archicad (port). If one is open already, it is brought to the front and False
    is returned."""
    global _instance_mutex
    kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _instance_mutex = kernel32.CreateMutexW(None, False, f"Local\\TapirDesignOptions_{PORT}")
    if kernel32.GetLastError() != 183:      # ERROR_ALREADY_EXISTS
        return True
    user32.FindWindowW.restype = ctypes.c_void_p
    hwnd = user32.FindWindowW(None, TITLE)
    if hwnd:
        user32.ShowWindow(ctypes.c_void_p(hwnd), 9)            # SW_RESTORE
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    return False


class ForegroundKeeper:
    """Windows: keeps the window on top of Archicad only. When another program comes to the front, the window goes
    right behind it; when Archicad (or the window itself) is in front, it is on top again. Other systems: always on top."""
    SWP = 0x0001 | 0x0002 | 0x0010          # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE

    def __init__(self, root):
        self.root, self.on_top = root, None
        self.windows = sys.platform == "win32"
        if not self.windows:
            self.root.attributes("-topmost", True)
            return
        from ctypes import wintypes
        self.user32, self.kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        self.user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self.user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_int, wintypes.UINT)
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.own_pid, self.archicad_pid = os.getpid(), archicad_process_id()
        self.name_cache = {}        # process id -> is the program name "archicad" (if the port gave no process)
        self.poll()

    def process_of(self, hwnd):
        pid = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def is_archicad(self, pid):
        if pid == self.own_pid or (self.archicad_pid and pid == self.archicad_pid):
            return True
        if self.archicad_pid:
            return False
        if pid not in self.name_cache:      # fallback: by program name
            name = ""
            h = self.kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
            if h:
                buffer, size = ctypes.create_unicode_buffer(1024), ctypes.c_ulong(1024)
                if self.kernel32.QueryFullProcessImageNameW(h, 0, buffer, ctypes.byref(size)):
                    name = buffer.value
                self.kernel32.CloseHandle(h)
            self.name_cache[pid] = "archicad" in os.path.basename(name).lower()
        return self.name_cache[pid]

    def is_topmost(self, hwnd):
        return bool(self.user32.GetWindowLongW(hwnd, -20) & 0x8)         # GWL_EXSTYLE, WS_EX_TOPMOST

    def poll(self):
        try:
            hwnd = self.user32.GetForegroundWindow()
            if hwnd:
                on_top = self.is_archicad(self.process_of(hwnd))
                own = int(self.root.wm_frame(), 16)
                if on_top:
                    if self.on_top is not True:
                        self.root.attributes("-topmost", True)
                # Another program is in front. Also fix it if Windows has made the window topmost meanwhile: a window
                # placed behind a topmost window (e.g. the Snipping Tool overlay) becomes topmost itself.
                elif self.on_top is not False or self.is_topmost(own):
                    self.root.attributes("-topmost", False)
                    self.user32.SetWindowPos(own, -2, 0, 0, 0, 0, self.SWP)               # HWND_NOTOPMOST
                    behind = self.user32.GetAncestor(hwnd, 3) or hwnd                     # GA_ROOTOWNER
                    if not self.is_topmost(behind):     # behind the other program (unless that one is topmost)
                        self.user32.SetWindowPos(own, behind, 0, 0, 0, 0, self.SWP)
                self.on_top = on_top
        except (tk.TclError, OSError, ValueError, ctypes.ArgumentError):
            pass
        self.root.after(300, self.poll)


# ---------------------------------------------------------------- user interface
class App:
    def __init__(self, root):
        self.root = root
        self.root.title(TITLE)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)     # from here on ForegroundKeeper keeps it on top of Archicad only
        self.info = {}
        self.option_sets = []       # design_option_sets()
        self.options = {}           # design option GUID -> {"guid", "id", "name", "set"}
        self.checks = {}            # design option GUID -> (BooleanVar, Checkbutton)
        self.elements = []
        self.list_loaded = False    # matrix: a list is loaded (it stays until Refresh)
        self.matrix_header = ""     # matrix: description of the selection the list was made from ("2 selected")
        self.active_rows = set()    # matrix: selected rows (Ctrl / Shift: more)
        self.anchor = None          # matrix: start row of a Shift-click (the last plain / Ctrl click)
        self.last_ac_selection = None   # matrix: the Archicad selection seen last (poll_selection())
        self.row_of_member = {}     # matrix: element GUID -> its row (every identical instance)
        self.foreground = None
        self.rows = {}              # matrix: row number -> matching_rows() row
        self.columns = []           # matrix: [{"place" (None = element name, MAIN, option GUID), "x0", "x1", "name", "color"}]
        self.set_bands = []         # matrix: design option sets in the header [(x0, x1, name, color)]
        self.thick_lines = []       # matrix: thick vertical lines (element name | main model | sets)
        self.table_width = self.row_height = 0
        self.size_state = None      # the window size rule applied last (fit_window())
        self.req_height = 0         # the requested content height at that time
        self.marks = {}             # matrix: (row, place) -> DELETE / ADD
        self.font = tkfont.nametofont("TkDefaultFont")
        self.bold_font = self.font.copy()
        self.bold_font.configure(weight="bold")
        self.mark_font = self.font.copy()          # the matrix marks (◉ ●) are larger, so they are easy to tell apart
        self.mark_font.configure(size=abs(self.font.actual("size")) + 4)
        self.small_font = self.font.copy()
        self.small_font.configure(size=max(7, abs(self.font.actual("size")) - 1))
        self.busy = False
        self.mode = tk.StringVar(value=MODE_COPY)
        self.view = tk.StringVar(value="copy")

        frame = ttk.Frame(self.root, padding=6)
        frame.pack(fill="both", expand=True)        # with a long list the window can be stretched (fit_window())
        ttk.Frame(frame, width=MIN_WIDTH, height=0).pack()      # minimum width: the title must fit

        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        for key, text in (("copy", "Copy"), ("matrix", "Matrix")):
            ttk.Radiobutton(bar, text=text, value=key, variable=self.view, style="Toolbutton",
                            command=self.switch_view).pack(side="left")
        self.refresh_icon = tk.PhotoImage(data=REFRESH_ICON)
        ttk.Button(bar, image=self.refresh_icon, style="Toolbutton", command=self.refresh).pack(side="right")
        self.project_label = ttk.Label(frame, text="", foreground="#555", wraplength=MIN_WIDTH)
        self.project_label.pack(anchor="w", pady=(4, 0))
        self.selection_label = ttk.Label(frame, text="", wraplength=MIN_WIDTH, foreground="#555")
        self.selection_label.pack(anchor="w", pady=(0, 4))

        # --- Copy view
        self.copy_frame = ttk.Frame(frame)
        self.options_frame = ttk.LabelFrame(self.copy_frame, text="Copy to", padding=(6, 2, 6, 4))
        self.options_frame.pack(fill="x")
        ttk.Radiobutton(self.copy_frame, text="Copy (original stays)", value=MODE_COPY,
                        variable=self.mode).pack(anchor="w", pady=(4, 0))
        ttk.Radiobutton(self.copy_frame, text="Move original to first, copy to rest", value=MODE_MOVE,
                        variable=self.mode).pack(anchor="w")
        self.copy_button = ttk.Button(self.copy_frame, text="Apply", command=self.on_copy_apply)
        self.copy_button.pack(fill="x", pady=(4, 2))

        # --- Matrix view
        self.matrix_frame = ttk.Frame(frame)
        self.table_frame = tk.Frame(self.matrix_frame, bd=0, highlightthickness=1, highlightbackground=THICK_LINE_COLOR)
        self.table_frame.pack(anchor="w", fill="y", expand=True)
        self.table_frame.rowconfigure(1, weight=1)
        self.header = tk.Canvas(self.table_frame, width=1, height=1, bg="white", highlightthickness=0, cursor="hand2")
        self.body = tk.Canvas(self.table_frame, width=1, height=1, bg="white", highlightthickness=0, cursor="hand2")
        self.scrollbar = ttk.Scrollbar(self.table_frame, command=self.body.yview)
        self.body.configure(yscrollcommand=self.scrollbar.set)
        self.header.grid(row=0, column=0, sticky="w")
        self.body.grid(row=1, column=0, sticky="nsw")
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.scrollbar.grid_remove()
        self.header.bind("<Button-1>", self.on_header_click)
        self.body.bind("<Button-1>", self.on_body_click)
        self.body.bind("<MouseWheel>", lambda e: self.body.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        ttk.Label(self.matrix_frame, text=f"{SELECTED} selected  {PRESENT} same elsewhere.  Click: {DELETE} delete, "
                                          f"{ADD} add. Header: add to all. Name: select (Ctrl / Shift: more rows, "
                                          f"then a cell marks the same kind of cell in all of them; Esc: none). "
                                          f"Refresh button: new list.",
                  foreground="#555", wraplength=MIN_WIDTH).pack(anchor="w", pady=(4, 0))
        self.matrix_button = ttk.Button(self.matrix_frame, text="Apply", command=self.on_matrix_apply)
        self.matrix_button.pack(fill="x", pady=(4, 2))

        ttk.Label(frame, text=AUTHOR, foreground="#a8a8a8", font=self.small_font).pack(side="bottom", anchor="e")
        self.result_label = ttk.Label(frame, text="", wraplength=MIN_WIDTH, justify="left")
        self.result_label.pack(side="bottom", anchor="w")

        self.root.bind("<FocusIn>", self.on_focus)
        self.root.bind("<Escape>", self.on_escape)
        self.switch_view(refresh=False)
        self.refresh()
        self.foreground = ForegroundKeeper(self.root)
        self.root.after(SELECTION_POLL_MS, self.poll_selection)
        self.unreachable = 0        # consecutive failed IsAlive checks (when the Archicad process is not known)
        self.root.after(ARCHICAD_WATCH_MS, self.watch_archicad)

    def watch_archicad(self):
        """The window closes when Archicad quits: by its process (Windows), or after 3 failed IsAlive checks."""
        pid = getattr(self.foreground, "archicad_pid", None)
        if pid:
            if not process_alive(pid):
                self.root.destroy()
                return
        elif not self.busy:
            try:
                send_command("API.IsAlive", timeout=2, wait=0)
                self.unreachable = 0
            except ArchicadError as e:
                self.unreachable += 0 if "busy" in str(e) else 1
                if self.unreachable >= 3:
                    self.root.destroy()
                    return
        self.root.after(ARCHICAD_WATCH_MS, self.watch_archicad)

    # ------------------------------------------------ common
    def show(self, lines):
        if len(lines) > MAX_MESSAGE_LINES:
            lines = lines[:MAX_MESSAGE_LINES - 1] + [f"… {len(lines) - MAX_MESSAGE_LINES + 1} more lines", lines[-1]]
        self.result_label.configure(text="\n".join(lines))
        self.fit_window(keep=True)

    def fit_window(self, keep=False):
        """The window fits its content and cannot be resized by hand - except when the matrix list is longer than
        VISIBLE_ROWS: then it can be stretched vertically, at most to the length of the list.
        keep: the height set by hand stays (clamped to the limits).
        The window is touched only if something changed (limits or requested size) - every needless geometry call
        makes the window flicker (e.g. when clicking a row)."""
        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()     # requested size (12 rows)
        extra = len(self.rows) - VISIBLE_ROWS
        if self.view.get() == "matrix" and self.list_loaded and extra > 0:
            smallest, largest = height - (VISIBLE_ROWS - 3) * self.row_height, height + extra * self.row_height
            state = ("stretch", width, smallest, largest)
            if state == self.size_state:
                return
            stretched = keep and self.size_state is not None and self.size_state[0] == "stretch"
            # the height set by hand stays; if the number of text lines changed, it follows by that much
            target = self.root.winfo_height() + height - self.req_height if stretched else None
            self.root.minsize(width, smallest)
            self.root.maxsize(width, largest)
            self.root.resizable(False, True)
            self.root.geometry(f"{width}x{min(max(target, smallest), largest)}" if target else "")
        else:
            state = ("fixed",)
            if state == self.size_state:
                return
            self.root.resizable(False, False)
            self.root.minsize(1, 1)
            self.root.maxsize(self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            self.root.geometry("")
        self.size_state, self.req_height = state, height
        self.root.update_idletasks()

    def option_names(self):
        names = {g: option_label(o) for g, o in self.options.items()}
        names[None] = "Main model"
        return names

    def switch_view(self, refresh=True):
        copy = self.view.get() == "copy"
        (self.matrix_frame if copy else self.copy_frame).pack_forget()
        if copy:
            self.copy_frame.pack(fill="x", before=self.result_label)
        else:
            self.matrix_frame.pack(fill="both", expand=True, before=self.result_label)
        self.show([])
        if refresh and self.info:
            if copy:
                self.reload_selection()
            elif self.list_loaded:
                self.show_matrix_summary()      # the loaded list stays (until Refresh)
            else:
                self.load_matrix()
        self.fit_window()

    def on_focus(self, event):
        # clicking back from Archicad: the selection may have changed (the matrix list stays until Refresh)
        if event.widget is self.root and self.info and not self.busy:
            self.reload_selection()

    def run_task(self, func, writes=True):
        """An Archicad operation: buttons disabled, wait cursor, result lines at the bottom. Returns success."""
        if writes and self.info.get("isTeamwork"):
            self.show(["Teamwork project – not supported."])
            return False
        self.busy = True
        for button in (self.copy_button, self.matrix_button):
            button.configure(state="disabled")
        self.root.configure(cursor="watch")
        self.show(["Working…"])
        self.root.update_idletasks()
        try:
            self.show(func())
            return True
        except ArchicadError as e:
            self.show([str(e)])
            return False
        finally:
            self.root.configure(cursor="")
            for button in (self.copy_button, self.matrix_button):
                button.configure(state="normal")
            self.busy = False

    def refresh(self):
        ticked = set(self.targets())
        for child in self.options_frame.winfo_children():
            child.destroy()
        self.checks = {}
        try:
            self.info = connect()
            option_sets = design_option_sets()
        except ArchicadError as e:
            self.info = {}
            self.project_label.configure(text=str(e))
            self.selection_label.configure(text="")
            return
        self.project_label.configure(text=self.info.get("projectName") or "(untitled)")
        self.option_sets = option_sets
        self.options = {o["guid"]: o for s in option_sets for o in s["options"]}
        for s in option_sets:
            if len(option_sets) > 1 or s["name"]:
                ttk.Label(self.options_frame, text=s["name"], foreground="#555").pack(anchor="w")
            for o in s["options"]:
                var = tk.BooleanVar(value=o["guid"] in ticked)
                check = ttk.Checkbutton(self.options_frame, text=option_label(o), variable=var)
                check.pack(anchor="w", padx=(10, 0))
                self.checks[o["guid"]] = (var, check)
        if not option_sets:
            ttk.Label(self.options_frame, text="No design options.").pack(anchor="w")
        if self.info.get("isTeamwork"):
            self.show(["Teamwork project – not supported."])
        self.reload_selection(force=True)

    def reload_selection(self, force=False):
        """Copy view: reads the selection again. Matrix view: a new list from the current selection only when forced
        (Refresh) - until then the loaded list stays (clicking a name changes the selection too)."""
        try:
            if self.view.get() == "copy":
                self.elements = read_selection()
                self.show_copy_selection()
            elif force:
                self.load_matrix()
        except ArchicadError as e:
            self.selection_label.configure(text=str(e))

    # ------------------------------------------------ Copy
    def targets(self):
        """GUIDs of the ticked design options in list order."""
        return [g for g, (var, _) in self.checks.items() if var.get()]

    def show_copy_selection(self):
        if not self.elements:
            text = "Nothing selected."
        else:
            text = f"{len(self.elements)} selected: {describe_types(Counter(e['type'] for e in self.elements))}"
            read_only = sum(1 for e in self.elements if not e["editable"])
            if read_only:
                text += f" ({read_only} hotlink, read-only)"
        self.selection_label.configure(text=text)
        count = Counter(e["option"] for e in self.elements)
        for g, (_, check) in self.checks.items():
            n = count.get(g, 0)
            check.configure(text=option_label(self.options[g]) + (f"  ({n} here)" if n else ""))

    def on_copy_apply(self):
        targets = self.targets()
        if not targets:
            self.show(["Tick at least one option."])
            return
        names = self.option_names()
        self.run_task(lambda: run_copy(targets, self.mode.get(), names))
        self.reload_selection(force=True)

    # ------------------------------------------------ Matrix
    def cell_text(self, row, place):
        r = self.rows[row]
        members = r["members"].get(place, [])
        mark = self.marks.get((row, place))
        if not members:
            return mark or ""
        base = SELECTED if any(g in r["selected"] for g in members) else PRESENT
        return (mark or base) + (str(len(members)) if len(members) > 1 else "")

    def load_matrix(self):
        """New list: the currently selected elements and the elements identical to them (stays until Refresh)."""
        rows = []
        self.marks = {}
        self.active_rows, self.anchor = set(), None

        def task():
            elements = read_selection()
            self.elements = elements
            # the list is made from this selection: it is not yet "a selection in the plan" (else every row is green)
            self.last_ac_selection = frozenset(e["guid"] for e in elements)
            rows.extend(matching_rows(elements, list(self.options)) if elements else [])
            with_host = len(elements) - sum(len(r["selected"]) for r in rows)
            self.matrix_header = (f"{len(elements)} selected" + (f" ({with_host} come with host)" if with_host else "")
                                  if elements else "Nothing selected.")
            return []

        self.run_task(task, writes=False)
        self.list_loaded = True
        self.build_table(rows)
        self.show_matrix_summary()

    def show_matrix_summary(self):
        elsewhere = sum(1 for r in self.rows.values() if len(r["members"]) > 1)
        self.selection_label.configure(text=self.matrix_header + (f" · {elsewhere} of {len(self.rows)} also elsewhere"
                                                                  if self.rows else ""))
        self.fit_window(keep=True)

    def build_table(self, rows, keep=False):
        """Matrix columns: element name | main model | the design options of each set (set name above them, thick
        lines between the groups); then drawing and window sizing (keep: the height stretched by hand stays)."""
        self.rows = dict(enumerate(rows))
        self.row_of_member = {g: i for i, r in self.rows.items() for v in r["members"].values() for g in v}
        self.row_height = h = max(self.font.metrics("linespace"), self.mark_font.metrics("linespace")) + 6

        def width_of(text):
            return max(40, self.font.measure(text) + 16)

        x = min(200, max([self.font.measure(r["label"]) for r in rows] + [self.font.measure("Element")]) + 16)
        self.columns = [{"place": None, "x0": 0, "x1": x, "name": "Element", "color": None},
                        {"place": MAIN, "x0": x, "x1": x + width_of("Main"), "name": "Main", "color": None}]
        self.thick_lines = [x, x + width_of("Main")]
        x = self.thick_lines[-1]
        self.set_bands = []
        for i, s in enumerate(s for s in self.option_sets if s["options"]):
            color = SET_BACKGROUNDS[i % len(SET_BACKGROUNDS)]
            widths = [width_of(option_label(o)) for o in s["options"]]
            missing = self.bold_font.measure(s["name"]) + 16 - sum(widths)      # the set name must fit too
            if missing > 0:
                n = len(widths)
                widths = [w + missing // n + (1 if j < missing % n else 0) for j, w in enumerate(widths)]
            x0 = x
            for o, w in zip(s["options"], widths):
                self.columns.append({"place": o["guid"], "x0": x, "x1": x + w, "name": option_label(o), "color": color})
                x += w
            self.set_bands.append((x0, x, s["name"], color))
            self.thick_lines.append(x)
        self.table_width = x
        self.thick_lines = [v for v in self.thick_lines if v < x]          # the frame is at the right edge
        self.header.configure(width=x, height=2 * h)
        self.body.configure(width=x, height=max(1, min(VISIBLE_ROWS, len(rows))) * h, yscrollincrement=h,
                            scrollregion=(0, 0, x, max(1, len(rows)) * h))
        if len(rows) > VISIBLE_ROWS:
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()
        if not keep:
            self.body.yview_moveto(0)
            self.size_state = None          # new list: the window returns to its natural size
        self.draw_header()
        self.draw_body()
        self.fit_window(keep=keep)

    def draw_header(self):
        c, h = self.header, self.row_height
        c.delete("all")
        for x0, x1, name, color in self.set_bands:
            c.create_rectangle(x0, 0, x1, 2 * h, fill=color, width=0)
            c.create_text((x0 + x1) / 2, h / 2, text=name, font=self.bold_font)
            c.create_line(x0, h, x1, h, fill=LINE_COLOR)
        for col in self.columns:
            if col["place"] is None:
                c.create_text(6, 1.5 * h, text=col["name"], anchor="w")
            else:
                c.create_text((col["x0"] + col["x1"]) / 2, 1.5 * h, text=col["name"])
            if col["color"] and col["x0"] not in self.thick_lines and col["x0"] > 0:
                c.create_line(col["x0"], h, col["x0"], 2 * h, fill=LINE_COLOR)
        for x in self.thick_lines:
            c.create_line(x, 0, x, 2 * h, fill=THICK_LINE_COLOR, width=2)
        c.create_line(0, 2 * h - 1, self.table_width, 2 * h - 1, fill=THICK_LINE_COLOR)

    def draw_body(self):
        c, h = self.body, self.row_height
        c.delete("all")
        total = max(1, len(self.rows)) * h
        for i, r in self.rows.items():
            y = i * h
            for col in self.columns:
                if col["place"] is None:
                    c.create_text(6, y + h / 2, text=self.elide(r["label"], col["x1"] - 12), anchor="w")
                    continue
                text = self.cell_text(i, col["place"])
                if text:
                    self.draw_mark(c, (col["x0"] + col["x1"]) / 2, y + h / 2, text[0], text[1:])
            c.create_line(0, y + h, self.table_width, y + h, fill=LINE_COLOR)
        for col in self.columns:
            if col["color"] and col["x0"] not in self.thick_lines:
                c.create_line(col["x0"], 0, col["x0"], total, fill=LINE_COLOR)
        for x in self.thick_lines:
            c.create_line(x, 0, x, total, fill=THICK_LINE_COLOR, width=2)
        self.draw_active_rows()

    def draw_mark(self, c, cx, cy, mark, count):
        """The mark of a cell: ✕ and + drawn from lines (same size and stroke, in the color of the mark), ◉ / ● as
        characters; count: if a cell holds more identical elements, the number goes next to the mark."""
        k, color = MARK_SIZE, MARK_COLORS[mark]
        cx, cy = round(cx - (4 if count else 0)), round(cy)      # whole pixels: sharp and symmetric
        if mark == DELETE:
            for y0, y1 in ((-k, k), (k, -k)):
                c.create_line(cx - k, cy + y0, cx + k + 1, cy + y1, fill=color, width=MARK_WIDTH, capstyle="round")
        elif mark == ADD:
            # two rectangles (drawn as lines the arms fall on half pixels and look uneven); as large as the ✕
            p, v = k + 1, MARK_WIDTH // 2
            c.create_rectangle(cx - p, cy - v, cx + p + 1, cy + v, fill=color, width=0)
            c.create_rectangle(cx - v, cy - p, cx + v, cy + p + 1, fill=color, width=0)
        else:
            c.create_text(cx, cy, text=mark, fill=color, font=self.mark_font)
        if count:
            c.create_text(cx + k + 6, cy, text=count, fill=color, font=self.font, anchor="w")

    def draw_active_rows(self):
        """Green background of the selected rows (whole row); only these items change, the table is not redrawn."""
        self.body.delete("active")
        for row in self.active_rows & set(self.rows):
            y = row * self.row_height
            self.body.create_rectangle(0, y, self.table_width, y + self.row_height, fill=ACTIVE_ROW_COLOR, width=0,
                                       tags="active")
        self.body.tag_lower("active")

    def elide(self, text, width):
        """The text cut to the given width (…)."""
        if self.font.measure(text) <= width:
            return text
        while text and self.font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    def column_at(self, x):
        return next((col for col in self.columns if col["x0"] <= x < col["x1"]), None)

    def on_body_click(self, event):
        row = int(self.body.canvasy(event.y) // self.row_height) if self.row_height else -1
        col = self.column_at(self.body.canvasx(event.x))
        if row not in self.rows or not col:
            return
        if col["place"] is None:
            self.select_row(row, shift=bool(event.state & 0x0001), ctrl=bool(event.state & 0x0004))
        elif row in self.active_rows and len(self.active_rows) > 1:
            # in a selected row the kind of the clicked cell decides - a circle (the element is there): ✕ on the
            # circles of the selected rows; an empty cell: + on the empty cells of the selected rows (where there is
            # something to copy). The other kind does not change. If all such cells are marked, the marks are removed.
            place = col["place"]
            present = bool(self.rows[row]["members"].get(place))
            similar = [r for r in sorted(self.active_rows & set(self.rows))
                       if bool(self.rows[r]["members"].get(place)) == present and (present or self.rows[r]["source"])]
            value = any((r, place) not in self.marks for r in similar)
            for r in similar:
                self.toggle_mark(r, place, value)
            self.draw_body()
        else:
            self.toggle_mark(row, col["place"])
            self.draw_body()

    def select_row(self, row, shift=False, ctrl=False):
        """Click on a name: only this row; Ctrl: row added / removed; Shift: every row from the previous click.
        The elements of the selected rows (every identical instance) get selected in Archicad too."""
        if shift and self.anchor in self.rows:
            first, last = sorted((self.anchor, row))
            self.active_rows = set(range(first, last + 1))
        elif ctrl:
            self.active_rows ^= {row}
            self.anchor = row
        else:
            self.active_rows, self.anchor = {row}, row
        self.sync_selection_to_archicad()

    def sync_selection_to_archicad(self):
        """Archicad selection = the elements of the selected rows (Archicad leaves out those in hidden options)."""
        rows = sorted(self.active_rows & set(self.rows))
        guids = [g for i in rows for v in self.rows[i]["members"].values() for g in v]
        try:
            now = selected_guids()
            tapir("ChangeSelectionOfElements", {"addElementsToSelection": [element_id(g) for g in guids if g not in now],
                                                "removeElementsFromSelection": [element_id(g) for g in now if g not in guids]})
            self.last_ac_selection = frozenset(selected_guids())    # the polling does not take this as a change
            visible = len(self.last_ac_selection & set(guids))
        except ArchicadError as e:
            self.show([str(e)])
            return
        self.draw_active_rows()
        if not rows:
            self.show([])
        elif len(rows) == 1:
            label = self.rows[rows[0]]["label"]
            self.show([f"Selected: {label}" if visible else f"{label}: not visible in this view."])
        else:
            self.show([f"Selected: {len(rows)} rows" + ("" if visible else " (not visible in this view)")])

    def on_escape(self, _event=None):
        """Esc: no row is selected (in Archicad either)."""
        if self.view.get() == "matrix" and self.active_rows and not self.busy:
            self.active_rows = set()
            self.sync_selection_to_archicad()

    def poll_selection(self):
        """Matrix: the rows follow the Archicad selection - the rows with any selected element are selected; none
        with an empty selection. Asks only with a loaded list, when no operation runs, and when Archicad (or this
        window) is in front. Skipped while Archicad is busy."""
        try:
            if (self.view.get() == "matrix" and self.list_loaded and self.rows and not self.busy
                    and getattr(self.foreground, "on_top", None) is not False):
                now = frozenset(selected_guids(timeout=1, wait=0))     # Archicad busy: skipped this time
                if now != self.last_ac_selection:
                    self.last_ac_selection = now
                    rows = {self.row_of_member[g] for g in now if g in self.row_of_member}
                    if rows != self.active_rows:
                        self.active_rows = rows
                        if len(rows) == 1:
                            self.anchor = next(iter(rows))
                        self.draw_active_rows()
        except ArchicadError:
            pass
        self.root.after(SELECTION_POLL_MS, self.poll_selection)

    def on_header_click(self, event):
        # clicking an option name (lower line) or "Main": the whole column
        col = self.column_at(event.x)
        if col and col["place"] is not None and (col["place"] == MAIN or event.y >= self.row_height):
            self.add_column(col["place"])

    def toggle_mark(self, row, place, value=None):
        """Marks / unmarks a cell (value: True / False = set / clear, None = toggle)."""
        r = self.rows[row]
        mark = DELETE if r["members"].get(place) else ADD
        if mark == ADD and not r["source"]:
            return                          # no editable selected element that could be copied
        if value is None:
            value = (row, place) not in self.marks
        if value:
            self.marks[(row, place)] = mark
        else:
            self.marks.pop((row, place), None)

    def add_column(self, place):
        """Header: every empty cell of the column marked for adding (if all are marked already, the marks go)."""
        rows = [i for i, r in self.rows.items() if not r["members"].get(place) and r["source"]]
        value = any((i, place) not in self.marks for i in rows)
        for i in rows:
            self.toggle_mark(i, place, value)
        self.draw_body()

    def on_matrix_apply(self):
        if not self.marks:
            self.show(["Nothing marked."])
            return
        additions, deletions = defaultdict(list), {}
        for (row, place), mark in self.marks.items():
            r = self.rows[row]
            if mark == ADD:
                additions[place or None].append(r["source"])
            else:
                deletions.update({g: place for g in r["members"][place]})
        types = {g: r["type"] for r in self.rows.values() for v in r["members"].values() for g in v}
        names = self.option_names()
        rows = list(self.rows.values())

        def task():
            result, new = apply_matrix(dict(additions), deletions, types, names)
            refresh_rows(rows, new)         # the list stays, only its members are refreshed
            return result

        if self.run_task(task):
            self.marks = {}
            self.build_table(rows, keep=True)
            self.show_matrix_summary()


if __name__ == "__main__":
    # Started by Tapir: hand over to an independent copy and exit at once (see relaunch_detached())
    if sys.platform == "win32" and not DETACHED and relaunch_detached():
        sys.exit(0)
    if sys.platform != "win32" or first_instance():
        root = tk.Tk()
        App(root)
        root.mainloop()
