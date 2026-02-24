"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              MAYA SUITE PRO FOR MAYA  –  v2.5                                ║
║                                                                              ║
║  Author  : Mouad EL MENDILI                                                  ║
║  Contact : Moadmaxe@gmail.com                                                ║
║  License : MIT – free to use, modify, and share                              ║
║                                                                              ║
║  ─── WANT TO HELP? ────────────────────────────────────────────────────────  ║
║  If you speak French, the easiest way to contribute is to translate          ║
║  the UI labels and warning messages to French, then open a Pull Request.     ║
║  Bug reports and fixes are always welcome too!                               ║
║  → github.com/moadmaxe/Maya-Suite-Pro                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

TOOLS INCLUDED:
  • Vertex Bevel      – live sliders, Maya-style vertex mode
  • Inset Faces       – fixed offset behaviour, individual face toggle
  • Extract Faces     – chip off with live offset
  • Separate Parts    – one-click poly separate
  • Select Similar    – normal / area / perimeter / topology
  • Soft Selection    – fixed: radius (ssd), mode (0/1); connected-only removed (unstable)
  • Quad Fill Pro     – Coons-patch hole filling with live preview
  • Smart Rename Tool – batch rename and group management
  • Shortest Path     – custom Dijkstra algorithm using edge length (geometric)

CHANGELOG v2.5:
  - Smart Rename Tool: "Add to Group" popup completely overhauled.
      * Now resizable and scrollable.
      * Group selection uses a proper scrollable list (textScrollList) – shows many groups.
      * UI matches suite dark theme with colored header and styled buttons.
      * Existing group list toggles visibility with radio buttons.
      * Fixed lambda callback error (added *args to radio button commands).
      * New Group now creates a group with exactly the name entered (no "_Collection" appended).
      * If a group with that name already exists, it is reused.
      * Auto-rename uses the entered name as base (numbers added automatically).
  - All other tools unchanged from v2.4.

CHANGELOG v2.4:
  - Soft Selection: removed the "Connected Only" checkbox due to persistent errors.
    The tool now offers toggle, radius slider, and falloff mode (surface/volume) only.
    All controls work reliably without causing further issues.
  - Shortest path now uses edge length (geometric distance) instead of edge count,
    ensuring it selects the true shortest path (matches Maya's default behavior).
  - Smart Rename Tool: added scroll layout to main window.
"""

import maya.cmds as cmds
import maya.mel  as mel
import re
import collections
import heapq

# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN GUARD
# ─────────────────────────────────────────────────────────────────────────────
try:
    cmds.loadPlugin("modelingToolkit", quiet=True)
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  (normalised 0-1 for Maya)
# ─────────────────────────────────────────────────────────────────────────────
C = {
    # section header backgrounds
    "hdr_quad"    : (0.10, 0.22, 0.32),   # deep navy
    "hdr_bevel"   : (0.18, 0.14, 0.30),   # deep violet
    "hdr_inset"   : (0.14, 0.26, 0.20),   # deep teal
    "hdr_extract" : (0.28, 0.18, 0.12),   # deep amber
    "hdr_select"  : (0.22, 0.22, 0.14),   # olive
    "hdr_soft"    : (0.12, 0.22, 0.28),   # slate
    "hdr_rename"  : (0.30, 0.20, 0.25),   # mauve
    # buttons
    "btn_primary" : (0.22, 0.46, 0.72),   # sky blue
    "btn_ok"      : (0.25, 0.55, 0.35),   # green
    "btn_warn"    : (0.65, 0.35, 0.15),   # amber
    "btn_danger"  : (0.60, 0.18, 0.18),   # red
    "btn_neutral" : (0.28, 0.28, 0.32),   # grey-blue
    # misc
    "ok_bg"       : (0.18, 0.42, 0.25),
    "err_bg"      : (0.55, 0.15, 0.15),
    "window_bg"   : (0.18, 0.18, 0.20),
}

# ─────────────────────────────────────────────────────────────────────────────
# SELECTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_faces():
    sel = cmds.ls(sl=True, fl=True) or []
    f   = [x for x in sel if '.f[' in x]
    return f or (cmds.filterExpand(selectionMask=34) or [])

def get_verts():
    sel = cmds.ls(sl=True, fl=True) or []
    v   = [x for x in sel if '.vtx[' in x]
    return v or (cmds.filterExpand(selectionMask=31) or [])

def get_edges():
    sel = cmds.ls(sl=True, fl=True) or []
    e   = [x for x in sel if '.e[' in x]
    return e or (cmds.filterExpand(selectionMask=32) or [])

def get_objects():
    return cmds.ls(sl=True, type='transform') or []

# ─────────────────────────────────────────────────────────────────────────────
# ① VERTEX BEVEL  (MayaStyle – live sliders, vertexComponent flag fix)
# ─────────────────────────────────────────────────────────────────────────────
def bevel_live():
    WIN = "bsp_bevel_live"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    sel = cmds.filterExpand(sm=31)
    if not sel:
        cmds.warning("⚠ Select vertices first.")
        return

    w = cmds.window(WIN, title="⬡  Vertex Bevel – Live", widthHeight=(400, 230), sizeable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label="▸ Select corner vertices  →  Click Apply  →  Drag sliders",
              align='left', height=28)

    # ── state holder ──
    node_holder = [None]

    slider_parent = cmds.columnLayout(adj=True)
    cmds.setParent('..')

    def apply_bevel(*_):
        vertices = cmds.filterExpand(sm=31)
        if not vertices:
            cmds.warning("⚠ Nothing selected.")
            return

        nodes = cmds.polyBevel(vertices)
        if not nodes:
            return
        node = nodes[0]
        node_holder[0] = node

        # Force vertex-bevel mode
        if cmds.objExists(node + ".vertexComponent"):
            cmds.setAttr(node + ".vertexComponent", 1)
        if cmds.objExists(node + ".offsetAsFraction"):
            cmds.setAttr(node + ".offsetAsFraction", 0)
        cmds.setAttr(node + ".offset",   0.2)
        cmds.setAttr(node + ".segments", 3)

        # rebuild slider area
        children = cmds.layout(slider_parent, q=True, ca=True) or []
        for ch in children:
            cmds.deleteUI(ch)
        cmds.setParent(slider_parent)

        cmds.separator(height=6, style='in')
        cmds.text(label="  Live Controls", align='left', font='boldLabelFont', height=22)
        cmds.attrFieldSliderGrp(label="Bevel Width", attribute=node + ".offset",
                                min=0.0, max=5.0, step=0.01,
                                columnWidth=[(1,100),(2,80),(3,180)])
        cmds.attrFieldSliderGrp(label="Segments",   attribute=node + ".segments",
                                min=1,   max=20,  step=1,
                                columnWidth=[(1,100),(2,80),(3,180)])
        cmds.refresh()

    cmds.button(label="▶  APPLY BEVEL", height=42, backgroundColor=C["btn_primary"],
                command=apply_bevel)
    cmds.separator(height=4, style='none')
    cmds.frameLayout(labelVisible=False, borderVisible=False,
                     collapsable=False, parent=w)
    cmds.setParent(slider_parent)
    cmds.setParent('..')

    cmds.separator(height=8, style='none')
    cmds.button(label="✕  Close", height=28, backgroundColor=C["btn_neutral"],
                command=lambda _: cmds.deleteUI(WIN))
    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# ② INSET FACES  (fixed: offset direction, keepFacesTogether logic)
# ─────────────────────────────────────────────────────────────────────────────
def inset_live():
    WIN = "bsp_inset_live"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    faces = get_faces()
    if not faces:
        cmds.warning("⚠ Select faces first.")
        return

    w = cmds.window(WIN, title="◈  Inset Faces – Live", widthHeight=(420, 240), sizeable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label="▸ Insets selected faces inward. Toggle individual mode below.",
              align='left', height=28)

    # ── Create extrude node ──
    # keepFacesTogether=1 → shared inset (Maya default)
    # localTranslateZ=0   → no extrusion, pure inset
    cmds.polyExtrudeFacet(faces, keepFacesTogether=1,
                          localTranslateZ=0, offset=0.2, ch=True)

    # Grab the most-recently created polyExtrudeFace node
    extrude_node = None
    history = cmds.listHistory(faces[0].split('.')[0]) or []
    for n in reversed(history):
        if cmds.nodeType(n) == 'polyExtrudeFace':
            extrude_node = n
            break

    if extrude_node:
        cmds.text(label="  ✔  Inset node created – drag slider to update",
                  backgroundColor=C["ok_bg"], height=24, align='left')
        cmds.separator(height=6, style='in')

        cmds.attrFieldSliderGrp(label="Inset Amount",
                                attribute=extrude_node + ".offset",
                                min=0.0, max=5.0, step=0.005,
                                columnWidth=[(1,100),(2,80),(3,180)])

        # keepFacesTogether: ON = grouped inset, OFF = individual per face
        def toggle_individual(val, *_):
            # val comes in as int (1=checked, 0=unchecked)
            cmds.setAttr(extrude_node + ".keepFacesTogether", int(val))

        cmds.checkBoxGrp(label="Grouped Inset",
                         numberOfCheckBoxes=1, value1=1,
                         annotation="ON = all faces inset together  |  OFF = each face inset individually",
                         changeCommand=toggle_individual)
    else:
        cmds.text(label="  ✘  Inset failed – check selection",
                  backgroundColor=C["err_bg"], height=24, align='left')

    cmds.separator(height=10, style='none')
    cmds.button(label="✕  Close", height=28, backgroundColor=C["btn_neutral"],
                command=lambda _: cmds.deleteUI(WIN))
    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# ③ EXTRACT FACES
# ─────────────────────────────────────────────────────────────────────────────
def extract_live():
    WIN = "bsp_extract_live"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    faces = get_faces()
    if not faces:
        cmds.warning("⚠ Select faces first.")
        return

    mesh = faces[0].split('.')[0]

    w = cmds.window(WIN, title="⬡  Extract Faces – Live", widthHeight=(420, 280), sizeable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label="▸ Extracts selected faces with an optional offset.",
              align='left', height=28)

    res = cmds.polyChipOff(faces, dup=True, off=0.0, ch=True)
    chip_node = next((n for n in (res or []) if cmds.nodeType(n) == 'polyChipOff'), None)

    if chip_node:
        cmds.text(label="  ✔  Extract node created",
                  backgroundColor=C["ok_bg"], height=24, align='left')
        cmds.separator(height=6, style='in')

        cmds.attrFieldSliderGrp(label="Offset",
                                attribute=chip_node + ".offset",
                                min=-5.0, max=5.0, step=0.01,
                                columnWidth=[(1,100),(2,80),(3,180)])

        cmds.checkBoxGrp(label="Keep Together", numberOfCheckBoxes=1, value1=1,
                         changeCommand=lambda v, *_: cmds.setAttr(chip_node + ".keepFacesTogether", int(v)))

        sep_check = cmds.checkBoxGrp(label="Separate Objects", numberOfCheckBoxes=1, value1=1)

        def apply_extract(*_):
            if cmds.checkBoxGrp(sep_check, q=True, value1=True):
                cmds.polySeparate(mesh, ch=False)
            cmds.inViewMessage(amg="Faces extracted & separated", pos="topCenter", fade=True)
            cmds.deleteUI(WIN)

        cmds.separator(height=6, style='in')
        cmds.button(label="✔  Apply & Separate", height=36, backgroundColor=C["btn_ok"],
                    command=apply_extract)
    else:
        cmds.text(label="  ✘  Extract failed",
                  backgroundColor=C["err_bg"], height=24, align='left')

    cmds.separator(height=6, style='none')
    cmds.button(label="✕  Close", height=28, backgroundColor=C["btn_neutral"],
                command=lambda _: cmds.deleteUI(WIN))
    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# ④ SELECT SIMILAR
# ─────────────────────────────────────────────────────────────────────────────
def select_similar_ui():
    WIN = "bsp_select_similar"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    faces  = get_faces()
    edges  = get_edges()
    verts  = get_verts()

    if faces:
        comp_type, mask, first = 'face', 0x0008, faces[0]
    elif edges:
        comp_type, mask, first = 'edge', 0x8000, edges[0]
    elif verts:
        comp_type, mask, first = 'vert', 0x0001, verts[0]
    else:
        cmds.warning("⚠ Select a face, edge, or vertex.")
        return

    w = cmds.window(WIN, title="◎  Select Similar", widthHeight=(320, 200), sizeable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label=f"  Component type: {comp_type}", align='left', height=26)
    cmds.separator(height=6, style='in')

    criteria = cmds.optionMenu(label="Criteria  ")
    for label in ("Normal", "Area", "Perimeter", "Topology"):
        cmds.menuItem(label=label)

    def apply(*_):
        crit = cmds.optionMenu(criteria, q=True, value=True)
        cmds.polySelectConstraint(disable=True)

        if crit == "Normal":
            if comp_type == 'face':
                info = cmds.polyInfo(first, faceNormals=True)
            elif comp_type == 'vert':
                info = cmds.polyInfo(first, vertexNormals=True)
            else:
                cmds.warning("Normal selection not supported for edges.")
                return
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", info[0])
            nx, ny, nz = float(nums[-3]), float(nums[-2]), float(nums[-1])
            cmds.polySelectConstraint(mode=3, type=mask, normal=True,
                                      normaldir=(nx, ny, nz))
        elif crit == "Area":
            cmds.polySelectConstraint(mode=3, type=mask, area=True, areaWeight=1)
        elif crit == "Perimeter":
            cmds.polySelectConstraint(mode=3, type=mask, perimeter=True)
        elif crit == "Topology":
            cmds.polySelectConstraint(mode=3, type=mask, topology=True)

        cmds.polySelectConstraint(disable=True)
        cmds.inViewMessage(amg=f"Selected similar  [{crit}]", pos="topCenter", fade=True)

    cmds.separator(height=8, style='none')
    cmds.button(label="▶  Apply", height=36, backgroundColor=C["btn_primary"], command=apply)
    cmds.button(label="✕  Close", height=28, backgroundColor=C["btn_neutral"],
                command=lambda _: cmds.deleteUI(WIN))
    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# ⑤ SOFT SELECTION  –  FINAL VERSION (without Connected Only)
# ─────────────────────────────────────────────────────────────────────────────
def softselect_tool():
    WIN = "bsp_softselect"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    # Create window with scroll layout
    window = cmds.window(WIN, title="⊙  Soft Selection Pro", widthHeight=(420, 300),
                         backgroundColor=C["window_bg"], sizeable=True)
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    # Header
    cmds.text(label="⚙️  SOFT SELECTION PRO", backgroundColor=C["hdr_soft"],
              height=28, align='left', font='boldLabelFont')
    cmds.separator(height=5, style='in')

    # Status indicator
    status_text = cmds.text(label="Status: Unknown", align='left', height=20)

    # ─── TOGGLE ──────────────────────────────────────────
    def toggle_soft(*args):
        current = cmds.softSelect(q=True, softSelectEnabled=True)
        cmds.softSelect(softSelectEnabled=not current)
        new_state = not current
        cmds.text(status_text, e=True, label=f"Status: {'ON' if new_state else 'OFF'}")
        cmds.inViewMessage(amg=f"Soft Select: {'ON' if new_state else 'OFF'}", pos="topCenter", fade=True)

    cmds.button(label="🔘  Toggle Soft Select (B)", height=36,
                backgroundColor=C["btn_primary"], command=toggle_soft)

    cmds.separator(height=8, style='none')

    # ─── RADIUS (ssd) ────────────────────────────────────
    def set_radius(val):
        try:
            if not cmds.softSelect(q=True, softSelectEnabled=True):
                cmds.warning("Soft Select is OFF. Enable it first.")
                return
            cmds.softSelect(ssd=float(val))
        except Exception as e:
            cmds.warning(f"Radius change failed: {e}")

    cmds.text(label="📏  FALLOFF RADIUS", backgroundColor=(0.22,0.22,0.14),
              height=24, align='left', font='boldLabelFont')
    cmds.floatSliderGrp(label="Radius", field=True,
                        minValue=0.01, maxValue=20.0, value=1.0,
                        columnWidth=[(1,80), (2,70), (3,180)],
                        changeCommand=set_radius)

    cmds.separator(height=8, style='none')

    # ─── FALLOFF MODE (softSelectFalloff: 0=surface, 1=volume) ───
    cmds.text(label="🔽  FALLOFF MODE", backgroundColor=(0.14,0.26,0.20),
              height=24, align='left', font='boldLabelFont')

    def set_mode(mode_val):
        def callback(*args):
            try:
                if not cmds.softSelect(q=True, softSelectEnabled=True):
                    cmds.warning("Soft Select is OFF. Enable it first.")
                    return
                cmds.softSelect(softSelectFalloff=mode_val)
                mode_name = "Surface" if mode_val == 0 else "Volume"
                cmds.inViewMessage(amg=f"Falloff Mode: {mode_name}", pos="topCenter", fade=True)
            except Exception as e:
                cmds.warning(f"Mode change failed: {e}")
        return callback

    # Query current mode to set initial selection
    current_mode = cmds.softSelect(q=True, softSelectFalloff=True) or 1
    initial_select = 2 if current_mode == 1 else 1  # Volume=2, Surface=1

    cmds.radioButtonGrp(label="Mode", numberOfRadioButtons=2,
                        labelArray2=["Surface", "Volume"], 
                        select=initial_select,
                        onCommand1=set_mode(0),
                        onCommand2=set_mode(1))

    cmds.separator(height=8, style='none')

    # Note: Connected Only option removed due to stability issues.

    cmds.separator(height=10, style='none')

    # Close button
    cmds.button(label="✕  Close", height=30, backgroundColor=C["btn_neutral"],
                command=lambda x: cmds.deleteUI(WIN))

    cmds.showWindow(window)


# ─────────────────────────────────────────────────────────────────────────────
# ⑥ QUAD FILL PRO  (Coons-patch, merged into main window)
# ─────────────────────────────────────────────────────────────────────────────
class QuadFillPro:  # v3.1-clean with normals fix
    """
    Quad Fill Pro – Coons-patch hole filler.

    UNDO DESIGN
    -----------
    Preview rebuilds use swf=False/True within a single synchronous Python call.
    Python is single-threaded: no UI event (Ctrl+Z included) can fire between
    swf=False and swf=True inside one function body.  The finally block always
    restores swf=True, even if an exception occurs, so undo is never left locked.
    Result: slider drags produce zero undo entries.  Finalize produces exactly one.

    ODD EDGE COUNT (5, 7, 9 …)
    ---------------------------
    Virtual-duplicate 5-pole technique: append a copy of the pole vertex to make
    the boundary even, run Coons normally, merge co-located verts on Finalize.
    Result: all-quad mesh with one 5-valence pole.  Offset slider = pole placement.
    """

    # ── state ────────────────────────────────────────────────────────────────
    def __init__(self):
        self.WIN            = "bsp_quad_fill"
        self.preview_plane  = None   # name of live preview mesh (or None)
        self.target_mesh    = None
        self.hole_pos       = []
        self.hole_verts     = []
        self._is_odd        = False
        self._hole_normal   = [0.0, 1.0, 0.0]
        # UI handles
        self.offset_slider  = None
        self.span_slider    = None
        self._status_text   = None
        self._offset_label  = None
        self._launch()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _launch(self):
        if cmds.window(self.WIN, exists=True):
            cmds.deleteUI(self.WIN)
        w = cmds.window(self.WIN, title="⬡  Quad Fill Pro",
                        widthHeight=(440, 360), sizeable=True)
        cmds.columnLayout(adj=True, rowSpacing=6, columnOffset=['both', 10])

        cmds.text(label=(
            "  ① Select the border edges of your hole\n"
            "  ② Click  [ Preview Grid ]\n"
            "  ③ Tweak Offset & Loop Cuts\n"
            "  ④ Click  [ Finalize & Merge ]"),
            align='left', height=66, font='smallBoldLabelFont')
        cmds.separator(height=4, style='in')

        self._status_text = cmds.text(
            label="  ─  Select border edges, then click  [ Preview Grid ]  ─",
            align='left', height=26, backgroundColor=(0.14, 0.14, 0.18))
        cmds.separator(height=4, style='none')

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 270])
        self._offset_label = cmds.text(label="  Rotation Offset:", align='right')
        self.offset_slider = cmds.intSliderGrp(
            field=True, minValue=0, maxValue=16, value=0,
            changeCommand=self._update, dragCommand=self._update,
            columnWidth=[(1,40),(2,190)])
        cmds.setParent('..')

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 270])
        cmds.text(label="  Loop Cuts (Sx):", align='right')
        self.span_slider = cmds.intSliderGrp(
            field=True, minValue=1, maxValue=8, value=4,
            changeCommand=self._update, dragCommand=self._update,
            columnWidth=[(1,40),(2,190)])
        cmds.setParent('..')
        cmds.separator(height=8, style='none')

        # Row 1 – main workflow buttons
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[140, 175, 95],
                       columnAlign3=['center','center','center'])
        cmds.button(label="① Preview Grid",     height=40,
                    backgroundColor=C["btn_primary"], command=self._start_preview)
        cmds.button(label="② Finalize & Merge", height=40,
                    backgroundColor=C["btn_ok"],    command=self._finalize)
        cmds.button(label="✕  Close",            height=40,
                    backgroundColor=C["btn_neutral"], command=self._close)
        cmds.setParent('..')

        cmds.showWindow(w)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _set_status(self, text, bg=(0.14, 0.14, 0.18)):
        if self._status_text and cmds.text(self._status_text, q=True, exists=True):
            cmds.text(self._status_text, e=True, label=text, backgroundColor=bg)

    def _set_offset_label(self, text):
        if self._offset_label and cmds.text(self._offset_label, q=True, exists=True):
            cmds.text(self._offset_label, e=True, label=text)

    # ── close ─────────────────────────────────────────────────────────────────
    def _close(self, *_):
        # Delete preview without touching undo (synchronous, safe)
        try:
            cmds.undoInfo(swf=False)
            if self.preview_plane and cmds.objExists(self.preview_plane):
                cmds.delete(self.preview_plane)
        finally:
            cmds.undoInfo(swf=True)
        self.preview_plane = None
        if cmds.window(self.WIN, exists=True):
            cmds.deleteUI(self.WIN)

    # ── ordered boundary verts ────────────────────────────────────────────────
    def _get_ordered_verts(self, edges):
        adj = {}
        for e in edges:
            evs = cmds.ls(cmds.polyListComponentConversion(e, toVertex=True),
                          flatten=True)
            if len(evs) == 2:
                adj.setdefault(evs[0], []).append(evs[1])
                adj.setdefault(evs[1], []).append(evs[0])
        if not adj:
            return [], []
        start = next(iter(adj))
        ordered, curr, prev = [start], start, None
        while len(ordered) < len(adj):
            nxt = next((n for n in adj[curr] if n != prev), None)
            if nxt is None:
                break
            ordered.append(nxt)
            prev, curr = curr, nxt
        return [cmds.xform(v, q=True, ws=True, t=True) for v in ordered], ordered

    # ── detect hole facing direction (average adjacent face normals) ──────────
    def _detect_hole_normal(self, edges):
        normals = []
        for e in edges:
            for f in cmds.ls(cmds.polyListComponentConversion(e, toFace=True),
                             flatten=True):
                info = cmds.polyInfo(f, faceNormals=True)
                if info:
                    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", info[0])
                    if len(nums) >= 3:
                        normals.append([float(nums[-3]),
                                        float(nums[-2]),
                                        float(nums[-1])])
        if not normals:
            return [0.0, 1.0, 0.0]
        avg = [sum(n[i] for n in normals) / len(normals) for i in range(3)]
        L   = (sum(x*x for x in avg)) ** 0.5
        return [x / L for x in avg] if L > 1e-6 else [0.0, 1.0, 0.0]

    # ── Newell's method – polygon winding normal ──────────────────────────────
    @staticmethod
    def _loop_normal(pts):
        nx = ny = nz = 0.0
        n = len(pts)
        for i in range(n):
            c, d = pts[i], pts[(i + 1) % n]
            nx += (c[1] - d[1]) * (c[2] + d[2])
            ny += (c[2] - d[2]) * (c[0] + d[0])
            nz += (c[0] - d[0]) * (c[1] + d[1])
        L = (nx*nx + ny*ny + nz*nz) ** 0.5
        return [nx/L, ny/L, nz/L] if L > 1e-9 else [0.0, 1.0, 0.0]

    # ── linear resample a curve to exactly n points ───────────────────────────
    @staticmethod
    def _resample(curve, n):
        if len(curve) == n:
            return curve
        out = []
        for i in range(n):
            t = i / max(n - 1, 1)
            s = t * (len(curve) - 1)
            j = min(int(s), len(curve) - 2)
            f = s - j
            out.append([curve[j][k] * (1 - f) + curve[j+1][k] * f
                        for k in range(3)])
        return out

    # ── build a Coons-patch plane ─────────────────────────────────────────────
    def _build_patch(self, vpos, effective_n, Sx, Sy, name):
        """
        Returns (transform_name, plane_bnd_indices).
        plane_bnd is the ordered list of boundary vertex indices on the plane,
        matching vpos[0..effective_n-1] in order.
        """
        plane = cmds.polyPlane(w=1, h=1, sx=Sx, sy=Sy, ch=False, name=name)[0]

        # Boundary index walk on the plane: bottom L→R, right B→T, top R→L, left T→B
        bnd = []
        for x in range(Sx + 1):       bnd.append(x)
        for y in range(1, Sy):         bnd.append(y * (Sx+1) + Sx)
        for x in range(Sx, -1, -1):   bnd.append(Sy * (Sx+1) + x)
        for y in range(Sy-1, 0, -1):  bnd.append(y * (Sx+1))

        for k in range(effective_n):
            cmds.xform(f"{plane}.vtx[{bnd[k]}]", ws=True, t=vpos[k])

        # Corners
        c00, c10 = vpos[0],        vpos[Sx]
        c11, c01 = vpos[Sx + Sy],  vpos[2*Sx + Sy]

        # Four boundary curves (each Sx+1 or Sy+1 points)
        bot   = vpos[0          : Sx + 1]
        right = vpos[Sx         : Sx + Sy + 1]
        top   = list(reversed(vpos[Sx + Sy : 2*Sx + Sy + 1]))

        # Left curve – close back to c00, then resample to Sy+1
        closed = all(abs(vpos[-1][i] - vpos[0][i]) < 1e-6 for i in range(3))
        raw_L  = vpos[2*Sx + Sy:] if closed else vpos[2*Sx + Sy:] + [vpos[0]]
        left   = self._resample(list(reversed(raw_L)), Sy + 1)

        # Coons interior
        total   = (Sx + 1) * (Sy + 1)
        bnd_set = set(bnd)
        for idx in range(total):
            if idx in bnd_set:
                continue
            col = idx % (Sx + 1)
            row = idx // (Sx + 1)
            u, v = col / float(Sx), row / float(Sy)
            B = bot[col]   if col < len(bot)   else bot[-1]
            T = top[col]   if col < len(top)   else top[-1]
            L = left[row]  if row < len(left)  else left[-1]
            R = right[row] if row < len(right) else right[-1]
            P = [
                (1-u)*L[i] + u*R[i] + (1-v)*B[i] + v*T[i]
                - ((1-u)*(1-v)*c00[i] + u*(1-v)*c10[i]
                 + (1-u)*v   *c01[i]  + u*v    *c11[i])
                for i in range(3)
            ]
            cmds.xform(f"{plane}.vtx[{idx}]", ws=True, t=P)

        # --- FIX: average all patch faces to determine orientation ---
        face_count = cmds.polyEvaluate(plane, face=True)
        avg_patch = [0.0, 0.0, 0.0]
        for f in range(face_count):
            info = cmds.polyInfo(f"{plane}.f[{f}]", faceNormals=True)
            if info:
                nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", info[0])
                if len(nums) >= 3:
                    avg_patch[0] += float(nums[-3])
                    avg_patch[1] += float(nums[-2])
                    avg_patch[2] += float(nums[-1])
        mag = (avg_patch[0]**2 + avg_patch[1]**2 + avg_patch[2]**2) ** 0.5
        if mag > 1e-6:
            avg_patch = [x/mag for x in avg_patch]
            dot = sum(avg_patch[i] * self._hole_normal[i] for i in range(3))
            if dot < 0:
                cmds.polyNormal(plane, normalMode=2, userNormalMode=0, ch=False)
        # --- end fix ---

        return plane, bnd

    # ── preview trigger ───────────────────────────────────────────────────────
    def _start_preview(self, *_):
        edges = cmds.ls(selection=True, flatten=True)
        if not edges:
            cmds.warning("⚠ Select border edges first.")
            return

        self.target_mesh      = edges[0].split('.')[0]
        vpos, vnames          = self._get_ordered_verts(edges)
        n                     = len(vnames)
        if n < 4:
            cmds.warning(f"⚠ Need at least 4 border edges (got {n}).")
            return

        self._hole_normal = self._detect_hole_normal(edges)
        self._is_odd      = (n % 2 != 0)

        # Enforce CCW winding relative to hole normal (axis-independent)
        ln  = self._loop_normal(vpos)
        dot = sum(ln[i] * self._hole_normal[i] for i in range(3))
        if dot < 0:
            vpos, vnames = list(reversed(vpos)), list(reversed(vnames))

        self.hole_pos    = vpos
        self.hole_verts  = vnames

        effective_n = n + 1 if self._is_odd else n
        cmds.intSliderGrp(self.offset_slider, e=True,
                          maxValue=max(1, n - 1), value=0)
        max_span = max(1, (effective_n // 2) - 1)
        cmds.intSliderGrp(self.span_slider, e=True,
                          maxValue=max_span, value=max(1, max_span // 2))

        if self._is_odd:
            self._set_status(
                f"  ⚠  ODD – {n} edges  │  5-pole at Offset  │  Slide to reposition",
                bg=(0.28, 0.18, 0.08))
            self._set_offset_label("  Pole Position:")
        else:
            self._set_status(
                f"  ✔  Even – {n} edges  │  Clean all-quad",
                bg=(0.10, 0.26, 0.14))
            self._set_offset_label("  Rotation Offset:")

        self._update()

    # ── rebuild preview ───────────────────────────────────────────────────────
    def _update(self, *_):
        if not self.hole_pos:
            return

        offset = cmds.intSliderGrp(self.offset_slider, q=True, v=True)
        Sx     = cmds.intSliderGrp(self.span_slider,   q=True, v=True)
        num_v  = len(self.hole_pos)
        vpos   = self.hole_pos[offset:] + self.hole_pos[:offset]

        if self._is_odd:
            vpos, effective_n = vpos + [vpos[0]], num_v + 1
        else:
            effective_n = num_v

        Sy = (effective_n - 2 * Sx) // 2
        if Sy < 1:
            cmds.warning("⚠ Loop Cuts too high – reduce Sx.")
            return

        # swf=False: every operation in this block is invisible to the undo queue.
        # SAFE because Python is single-threaded – no UI event can interrupt a
        # running function.  The finally block ALWAYS restores swf=True.
        try:
            cmds.undoInfo(swf=False)
            if self.preview_plane and cmds.objExists(self.preview_plane):
                cmds.delete(self.preview_plane)
                self.preview_plane = None
            self.preview_plane, _ = self._build_patch(
                vpos, effective_n, Sx, Sy, name="QuadFillPreview")
        finally:
            cmds.undoInfo(swf=True)

    # ── finalize & merge ──────────────────────────────────────────────────────
    def _finalize(self, *_):
        if not self.target_mesh or not self.hole_pos:
            cmds.warning("⚠ Click  [ Preview Grid ]  first.")
            return

        target     = self.target_mesh
        hole_pos   = list(self.hole_pos)
        hole_verts = list(self.hole_verts)
        is_odd     = self._is_odd
        offset     = cmds.intSliderGrp(self.offset_slider, q=True, v=True)
        Sx         = cmds.intSliderGrp(self.span_slider,   q=True, v=True)

        vpos       = hole_pos[offset:] + hole_pos[:offset]
        vnames_rot = hole_verts[offset:] + hole_verts[:offset]

        if is_odd:
            vpos, effective_n = vpos + [vpos[0]], len(hole_pos) + 1
        else:
            effective_n = len(hole_pos)

        Sy = (effective_n - 2 * Sx) // 2
        if Sy < 1:
            cmds.warning("⚠ Invalid spans – re-open Preview and adjust Loop Cuts.")
            return

        cmds.undoInfo(openChunk=True, chunkName="QuadFill")
        try:
            # Delete preview inside the chunk (undo restores it if user hits Ctrl+Z)
            try:
                cmds.undoInfo(swf=False)
                if self.preview_plane and cmds.objExists(self.preview_plane):
                    cmds.delete(self.preview_plane)
            finally:
                cmds.undoInfo(swf=True)
            self.preview_plane = None

            N_target = cmds.polyEvaluate(target, vertex=True)
            patch, plane_bnd = self._build_patch(
                vpos, effective_n, Sx, Sy, name="QuadFillPatch")

            cmds.select([target, patch])
            combined = cmds.polyUnite(ch=False)[0]

            # Targeted seam merge – only weld the exact boundary verts,
            # never touching the rest of the mesh (preserves roundness, other shells)
            seam = []
            for bi in plane_bnd:
                seam.append(f"{combined}.vtx[{N_target + bi}]")
            for vn in vnames_rot:
                m = re.search(r'\[(\d+)\]', vn)
                if m:
                    seam.append(f"{combined}.vtx[{m.group(1)}]")
            cmds.select(seam)
            cmds.polyMergeVertex(d=0.0001, ch=False)

            # Normals are already correct on the patch (set in _build_patch).
            # Do NOT recompute on the whole combined mesh — that would reset
            # the original mesh normals based on winding and flip everything.
            cmds.select(combined)

        finally:
            cmds.undoInfo(closeChunk=True)

        self.target_mesh = None
        self.hole_pos    = []
        self.hole_verts  = []
        self._is_odd     = False

        cmds.inViewMessage(
            amg="✔  Quad fill done!" + ("  (5-pole)" if is_odd else ""),
            pos="topCenter", fade=True)


# ─────────────────────────────────────────────────────────────────────────────
# ⑦ CUSTOM SHORTEST PATH (NO UV MODE) – UPDATED TO USE EDGE LENGTH
# ─────────────────────────────────────────────────────────────────────────────
def dijkstra_shortest_path(mesh, start_vert, end_vert, use_edge_length=False):
    """
    Find shortest edge path between two vertices using Dijkstra's algorithm.
    If use_edge_length is True, weight = edge length; otherwise weight = 1.
    Returns list of edge names, or None if no path exists.
    """
    # Build graph: vertex -> {neighbor: (edge, weight)}
    graph = {}
    edges = cmds.ls(cmds.polyListComponentConversion(mesh, toEdge=True), flatten=True)

    for edge in edges:
        verts = cmds.ls(cmds.polyListComponentConversion(edge, toVertex=True), flatten=True)
        if len(verts) == 2:
            v1, v2 = verts[0], verts[1]
            if v1 not in graph:
                graph[v1] = {}
            if v2 not in graph:
                graph[v2] = {}
            weight = 1
            if use_edge_length:
                # Calculate edge length
                pos1 = cmds.xform(v1, q=True, ws=True, t=True)
                pos2 = cmds.xform(v2, q=True, ws=True, t=True)
                weight = sum((a-b)**2 for a,b in zip(pos1, pos2)) ** 0.5
            graph[v1][v2] = (edge, weight)
            graph[v2][v1] = (edge, weight)

    if start_vert not in graph or end_vert not in graph:
        return None

    distances = {start_vert: 0}
    previous = {}
    pq = [(0, start_vert)]
    visited = set()

    while pq:
        dist, current = heapq.heappop(pq)
        if current in visited:
            continue
        visited.add(current)

        if current == end_vert:
            break

        for neighbor, (edge, weight) in graph[current].items():
            new_dist = dist + weight
            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                previous[neighbor] = (current, edge)
                heapq.heappush(pq, (new_dist, neighbor))

    if end_vert not in previous and start_vert != end_vert:
        return None

    path_edges = []
    current = end_vert
    while current in previous:
        prev_vert, edge = previous[current]
        path_edges.append(edge)
        current = prev_vert

    path_edges.reverse()
    return path_edges

def select_shortest_path_custom(*args):
    """
    Custom shortest path selection that stays in edge component mode.
    """
    # Get selected vertices
    sel = cmds.ls(sl=True, fl=True)
    verts = [v for v in sel if '.vtx[' in v]
    if not verts:
        verts = cmds.filterExpand(selectionMask=31) or []

    if len(verts) != 2:
        cmds.warning("Select exactly two vertices on the same mesh.")
        return

    # Ensure they're on the same mesh
    mesh1 = verts[0].split('.')[0]
    mesh2 = verts[1].split('.')[0]
    if mesh1 != mesh2:
        cmds.warning("Both vertices must belong to the same mesh.")
        return

    # Find shortest path using edge length (geometric distance) for accuracy
    path_edges = dijkstra_shortest_path(mesh1, verts[0], verts[1], use_edge_length=True)

    # Debug output
    if path_edges:
        print("Shortest path edges (by geometric distance):")
        for e in path_edges:
            print("   ", e)
    else:
        cmds.warning("No path found between the selected vertices.")
        return

    # Select the path
    cmds.select(path_edges, replace=True)

    # Force back to edge component selection mode
    cmds.selectMode(component=True)
    cmds.selectType(edge=True)

    cmds.inViewMessage(amg=f"Selected path with {len(path_edges)} edges",
                       pos="topCenter", fade=True)

# ─────────────────────────────────────────────────────────────────────────────
# ⑧ SMART RENAME TOOL – COMPLETE & CLEAN
# ─────────────────────────────────────────────────────────────────────────────
RENAME_MAIN = "RenameGroupMain"
RENAME_POPUP = "GroupPopup"

def get_groups():
    groups = []
    transforms = cmds.ls(type="transform", long=True)
    for t in transforms:
        children = cmds.listRelatives(t, children=True, fullPath=True)
        if not children:
            continue
        shapes = cmds.listRelatives(t, shapes=True, fullPath=True)
        if not shapes or len(children) > len(shapes):
            groups.append(cmds.ls(t, shortNames=True)[0])
    return sorted(set(groups))

def next_index(base):
    pattern = re.compile(rf"{base}_(\d+)$")
    highest = 0
    for obj in cmds.ls(transforms=True):
        m = pattern.match(obj)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1

def rename_objects(base, group=None):
    sel = cmds.ls(sl=True, transforms=True)
    if not sel:
        cmds.warning("Nothing selected.")
        return
    start = next_index(base)
    renamed = []
    for i, obj in enumerate(sel, start):
        new = f"{base}_{i:03d}"
        new = cmds.rename(obj, new)
        shapes = cmds.listRelatives(new, s=True, f=True) or []
        for s in shapes:
            try:
                cmds.rename(s, new + "Shape")
            except:
                pass
        if group:
            cmds.parent(new, group)
        renamed.append(new)
    cmds.select(renamed)

def rename_only(*args):
    result = cmds.promptDialog(
        title="Rename",
        message="Enter Name:",
        button=["OK", "Cancel"],
        defaultButton="OK",
        cancelButton="Cancel"
    )
    if result == "OK":
        name = cmds.promptDialog(q=True, text=True)
        if name:
            rename_objects(name)

def open_group_popup(*args):
    if cmds.window(RENAME_POPUP, exists=True):
        cmds.deleteUI(RENAME_POPUP)
    cmds.window(RENAME_POPUP, title="Add To Group", widthHeight=(360, 400), sizeable=True)
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label="➕  ADD TO GROUP", backgroundColor=C["hdr_rename"],
              height=26, align='left', font='boldLabelFont')
    cmds.separator(height=5, style='in')

    cmds.radioCollection("mode")
    cmds.radioButton("existingRB", label="Add to Existing Group", select=True,
                     changeCommand=lambda *args: toggle_group_ui(True))
    cmds.radioButton("newRB", label="Add selected to a new group",
                     changeCommand=lambda *args: toggle_group_ui(False))

    cmds.text(label="Select Group:")
    group_list = cmds.textScrollList("groupList", allowMultiSelection=False,
                                      height=150, backgroundColor=(0.25,0.25,0.27))
    groups = get_groups()
    if groups:
        cmds.textScrollList(group_list, e=True, append=groups)
    else:
        cmds.textScrollList(group_list, e=True, append=["-- No Groups Found --"])

    cmds.checkBox("autoNameCB", label="Auto naming from group name", value=True)

    cmds.separator(height=8, style='none')

    new_group_frame = cmds.frameLayout(label="New Group", visible=False, collapsable=False,
                                       marginWidth=5, marginHeight=5)
    cmds.columnLayout(adj=True, rowSpacing=5)
    cmds.textField("nameField", placeholderText="Group name")
    cmds.setParent('..')
    cmds.setParent('..')

    cmds.separator(height=10, style='none')

    cmds.button(label="Apply", height=35, backgroundColor=C["btn_primary"],
                command=apply_group_action)

    cmds.separator(height=5, style='none')

    cmds.button(label="Cancel", height=30, backgroundColor=C["btn_neutral"],
                command=lambda x: cmds.deleteUI(RENAME_POPUP))

    def toggle_group_ui(use_existing):
        cmds.frameLayout(new_group_frame, e=True, visible=not use_existing)
        cmds.textScrollList(group_list, e=True, enable=use_existing)

    cmds.showWindow(RENAME_POPUP)

def split_by_group(selection, group):
    inside = []
    outside = []
    for obj in selection:
        parents = cmds.listRelatives(obj, parent=True, fullPath=True) or []
        if parents and group in parents[0]:
            inside.append(obj)
        else:
            outside.append(obj)
    return inside, outside

def rename_and_parent(base, group, objects):
    start = next_index(base)
    renamed = []
    for i, obj in enumerate(objects, start):
        new = f"{base}_{i:03d}"
        new = cmds.rename(obj, new)
        shapes = cmds.listRelatives(new, s=True, f=True) or []
        for s in shapes:
            try:
                cmds.rename(s, new + "Shape")
            except:
                pass
        try:
            cmds.parent(new, group)
        except:
            pass
        renamed.append(new)
    cmds.select(renamed)

def process_group_add(base, group):
    sel = cmds.ls(sl=True, transforms=True)
    if not sel:
        cmds.warning("Nothing selected.")
        return
    inside, outside = split_by_group(sel, group)
    if inside and outside:
        msg = "Already inside group:\n\n" + "\n".join(inside)
        result = cmds.confirmDialog(
            title="Objects already in group",
            message=msg,
            button=["Rename ALL", "Add Missing Only", "Unselect Existing", "Cancel"],
            defaultButton="Add Missing Only",
            cancelButton="Cancel"
        )
        if result == "Cancel":
            return
        if result == "Unselect Existing":
            cmds.select(outside)
            return
        if result == "Add Missing Only":
            sel = outside
    rename_and_parent(base, group, sel)

def apply_group_action(*args):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select objects first.")
        return
    existing = cmds.radioButton("existingRB", q=True, select=True)
    if existing:
        selected = cmds.textScrollList("groupList", q=True, selectItem=True)
        if not selected or "-- No Groups" in selected[0]:
            cmds.warning("Select a valid group.")
            return
        group = selected[0]
        auto = cmds.checkBox("autoNameCB", q=True, value=True)
        if auto:
            base = group
        else:
            base = cmds.textField("nameField", q=True, text=True)
            if not base:
                cmds.warning("Enter a name.")
                return
        process_group_add(base, group)
    else:
        base = cmds.textField("nameField", q=True, text=True)
        if not base:
            cmds.warning("Name required.")
            return
        desired_group = base
        auto = cmds.checkBox("autoNameCB", q=True, value=True)

        # Create or reuse group
        if cmds.objExists(desired_group):
            group = desired_group
        else:
            group = cmds.group(em=True, name=desired_group)

        if auto:
            # Rename selected objects with base and sequential numbers
            start = next_index(base)
            renamed = []
            for i, obj in enumerate(sel, start):
                new_name = f"{base}_{i:03d}"
                try:
                    new = cmds.rename(obj, new_name)
                except:
                    continue
                shapes = cmds.listRelatives(new, s=True, f=True) or []
                for s in shapes:
                    try:
                        cmds.rename(s, new + "Shape")
                    except:
                        pass
                renamed.append(new)
            # Parent renamed objects to group
            for obj in renamed:
                try:
                    cmds.parent(obj, group)
                except:
                    pass
            if renamed:
                cmds.select(renamed)
        else:
            # No renaming, just parent original selection
            for obj in sel:
                try:
                    cmds.parent(obj, group)
                except:
                    pass
            cmds.select(sel)

    cmds.deleteUI(RENAME_POPUP)

def build_rename_main():
    if cmds.window(RENAME_MAIN, exists=True):
        cmds.deleteUI(RENAME_MAIN)
    cmds.window(RENAME_MAIN, title="Smart Rename Tool", widthHeight=(260, 140), sizeable=True)
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adj=True, rowSpacing=10)
    cmds.button(label="Rename All Selected", height=40, command=rename_only)
    cmds.button(label="Add To Group", height=40, command=open_group_popup)
    cmds.showWindow(RENAME_MAIN)

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def separate_loose():
    objs = get_objects()
    if objs:
        for obj in objs:
            cmds.polySeparate(obj, ch=False)
        cmds.inViewMessage(amg="Separated loose parts", pos="topCenter", fade=True)
    else:
        cmds.warning("⚠ Select an object first.")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION HEADER  helper
# ─────────────────────────────────────────────────────────────────────────────
def _section(icon, title, color):
    cmds.separator(height=6, style='none')
    cmds.text(
        label=f"  {icon}  {title.upper()}",
        backgroundColor=color,
        align='left',
        height=26,
        font='boldLabelFont'
    )

def _btn(label, color, fn):
    cmds.button(label=label, height=32, backgroundColor=color,
                command=lambda _: fn())

# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
def main_ui():
    WIN = "bsp_main"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    w = cmds.window(WIN, title="  Maya Suite Pro  –  Mouad",
                    widthHeight=(440, 720), sizeable=True,
                    backgroundColor=C["window_bg"])

    cmds.scrollLayout(childResizable=True, backgroundColor=C["window_bg"])
    cmds.columnLayout(adj=True, rowSpacing=4, columnOffset=['both', 8])

    # ── MASTER HEADER ───────────────────────────────────────────────────────
    cmds.text(
        label="  ⬡  MAYA SUITE PRO  –  v2.5",
        backgroundColor=(0.08, 0.12, 0.22),
        height=36,
        font='boldLabelFont',
        align='left'
    )
    cmds.text(
        label="  by Mouad  ·  github.com/mouadmaxe/Maya-Suite-Pro",
        backgroundColor=(0.10, 0.14, 0.24),
        height=20,
        align='left'
    )
    cmds.separator(height=10, style='in')

    # ══ QUAD FILL PRO ════════════════════════════════════════════════════════
    _section("⬡", "Quad Fill Pro", C["hdr_quad"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(
        label=(
            "  ① Select border edges of hole\n"
            "  ② Click 'Quad Fill Window' to open the tool"
        ),
        align='left', height=38
    )
    cmds.button(label="⬡  Open Quad Fill Pro Window", height=38,
                backgroundColor=C["btn_primary"],
                command=lambda _: QuadFillPro())
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ SMART RENAME TOOL ════════════════════════════════════════════════════
    _section("🏷️", "Smart Rename", C["hdr_rename"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(
        label=(
            "  Batch rename objects and manage groups.\n"
            "  Opens a separate window."
        ),
        align='left', height=34
    )
    cmds.button(label="🏷️  Open Smart Rename Tool", height=38,
                backgroundColor=C["btn_primary"],
                command=lambda _: build_rename_main())
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ BEVEL ════════════════════════════════════════════════════════════════
    _section("⬡", "Vertex Bevel", C["hdr_bevel"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(label="  Select corner vertices first.", align='left', height=22)
    _btn("⬡  Vertex Bevel  –  Live Sliders", C["btn_primary"], bevel_live)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ INSET ════════════════════════════════════════════════════════════════
    _section("◈", "Inset Faces", C["hdr_inset"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(label="  Select faces first.", align='left', height=22)
    _btn("◈  Inset Faces  –  Live + Individual Toggle", C["btn_ok"], inset_live)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ EXTRACT ══════════════════════════════════════════════════════════════
    _section("⬡", "Extract", C["hdr_extract"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(label="  Select faces first.", align='left', height=22)
    _btn("⬡  Extract Faces  –  Live Offset", C["btn_warn"], extract_live)
    _btn("⬡  Separate Loose Parts",          C["btn_neutral"], separate_loose)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ SELECTION ════════════════════════════════════════════════════════════
    _section("◎", "Selection", C["hdr_select"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    _btn("◎  Shortest Edge Path (Geometric)", C["btn_primary"], select_shortest_path_custom)
    _btn("◎  Select Similar …",                 C["btn_neutral"], select_similar_ui)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ SOFT SELECTION – FINAL VERSION (without Connected Only) ═══════════════
    _section("⊙", "Soft Selection", C["hdr_soft"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    _btn("⊙  Soft Selection Controls (FIXED)", C["btn_primary"], softselect_tool)
    cmds.setParent('..')
    cmds.setParent('..')

    # ── FOOTER ───────────────────────────────────────────────────────────────
    cmds.separator(height=12, style='in')
    cmds.text(
        label=(
            "  ★  Want to contribute?  Translate the UI to French or fix bugs!\n"
            "  → Open a Pull Request on GitHub  ·  Any help appreciated  ★"
        ),
        backgroundColor=(0.08, 0.14, 0.10),
        align='left', height=40
    )
    cmds.separator(height=6, style='none')

    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# Run the main UI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main_ui()
