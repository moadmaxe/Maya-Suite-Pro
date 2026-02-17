"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              BLENDER SUITE PRO FOR MAYA  –  v2.0                             ║
║                                                                              ║
║  Author  : Mouad EL MENDILI                                                  ║
║  Contact : Moadmaxe@gmail.com                                                ║
║  License : MIT – free to use, modify, and share                              ║
║                                                                              ║
║  ─── WANT TO HELP? ────────────────────────────────────────────────────────  ║
║  If you speak French, the easiest way to contribute is to translate          ║
║  the UI labels and warning messages to French, then open a Pull Request.     ║
║  Bug reports and fixes are always welcome too!                               ║
║  → github.com/mouad/blender-suite-pro  (replace with your actual URL)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

TOOLS INCLUDED:
  • Vertex Bevel      – live sliders, Blender-style vertex mode
  • Inset Faces       – fixed offset behaviour, individual face toggle
  • Extract Faces     – chip off with live offset
  • Separate Parts    – one-click poly separate
  • Select Similar    – normal / area / perimeter / topology
  • Soft Selection    – radius + falloff controls
  • Dissolve          – verts / edges / faces
  • Quad Fill Pro     – Coons-patch hole filling with live preview

CHANGELOG v2.0:
  - Merged Quad Fill Pro into main window (top section)
  - Replaced old bevel with BlenderStyleBevel (vertexComponent flag fix)
  - Fixed Inset tool (offset clamp, keepFacesTogether logic corrected)
  - Removed Loop Cut, Knife, Spin (unused)
  - Full UI overhaul: dark theme, colour-coded sections, emoji icons
"""

import maya.cmds as cmds
import maya.mel  as mel
import re

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
    "hdr_dissolve": (0.28, 0.12, 0.12),   # deep red
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
# ① VERTEX BEVEL  (BlenderStyle – live sliders, vertexComponent flag fix)
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
    # keepFacesTogether=1 → shared inset (Blender default)
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
# ⑤ SOFT SELECTION
# ─────────────────────────────────────────────────────────────────────────────
def softselect_tool():
    WIN = "bsp_softselect"
    if cmds.window(WIN, q=True, exists=True):
        cmds.deleteUI(WIN)

    w = cmds.window(WIN, title="⊙  Soft Selection", widthHeight=(380, 210), sizeable=True)
    cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

    cmds.text(label="  Proportional / Soft Selection Controls",
              align='left', height=26, font='boldLabelFont')
    cmds.separator(height=6, style='in')

    def toggle(*_):
        cur = cmds.softSelect(q=True, softSelectEnabled=True)
        cmds.softSelect(softSelectEnabled=not cur)
        state = "ON" if not cur else "OFF"
        cmds.inViewMessage(amg=f"Soft Select: {state}", pos="topCenter", fade=True)

    cmds.button(label="⇄  Toggle Soft Select  (hotkey: B)", height=36,
                backgroundColor=C["btn_primary"], command=toggle)

    cmds.floatSliderGrp(label="Falloff Radius", field=True,
                        min=0.0, max=20.0, value=1.0,
                        columnWidth=[(1,110),(2,70),(3,160)],
                        changeCommand=lambda v: cmds.softSelect(ssf=v))

    cmds.radioButtonGrp(label="Falloff Mode", numberOfRadioButtons=2,
                        labelArray2=["Volume", "Surface"], select=1,
                        onCommand1=lambda _: cmds.softSelect(sfd="volume"),
                        onCommand2=lambda _: cmds.softSelect(sfd="surface"))

    cmds.checkBox(label="Connected Vertices Only  (Alt+O)",
                  changeCommand=lambda v: cmds.softSelect(softSelectConnected=v))

    cmds.separator(height=8, style='none')
    cmds.button(label="✕  Close", height=28, backgroundColor=C["btn_neutral"],
                command=lambda _: cmds.deleteUI(WIN))
    cmds.showWindow(w)

# ─────────────────────────────────────────────────────────────────────────────
# ⑥ DISSOLVE UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def dissolve_verts():
    verts = get_verts()
    if verts:
        cmds.polyMergeVertex(verts, distance=0.0001, ch=False, alwaysMergeTwoVertices=True)
        cmds.inViewMessage(amg="Vertices dissolved", pos="topCenter", fade=True)
    else:
        cmds.warning("⚠ Select vertices first.")

def dissolve_edges():
    edges = get_edges()
    if edges:
        cmds.polyDelEdge(edges, ch=False, cleanVertices=True)
        cmds.inViewMessage(amg="Edges dissolved", pos="topCenter", fade=True)
    else:
        cmds.warning("⚠ Select edges first.")

def dissolve_faces():
    faces = get_faces()
    if faces:
        cmds.polyDelFacet(faces, ch=False)
        cmds.inViewMessage(amg="Faces dissolved", pos="topCenter", fade=True)
    else:
        cmds.warning("⚠ Select faces first.")

def separate_loose():
    objs = get_objects()
    if objs:
        for obj in objs:
            cmds.polySeparate(obj, ch=False)
        cmds.inViewMessage(amg="Separated loose parts", pos="topCenter", fade=True)
    else:
        cmds.warning("⚠ Select an object first.")

def shortest_path():
    mel.eval('SelectShortestEdgePathTool')

# ─────────────────────────────────────────────────────────────────────────────
# ⑦ QUAD FILL PRO  (Coons-patch, merged into main window)
# ─────────────────────────────────────────────────────────────────────────────
class QuadFillPro:
    """
    Select border edges of a hole → Preview Grid → adjust sliders → Finalize & Merge.
    Uses a Coons-patch interpolation for smooth interior vertices.
    """

    def __init__(self):
        self.WIN          = "bsp_quad_fill"
        self.preview_plane = None
        self.target_mesh  = None
        self.hole_pos     = []
        self.hole_verts   = []
        self.offset_slider = None
        self.span_slider   = None
        self._launch()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _launch(self):
        if cmds.window(self.WIN, exists=True):
            cmds.deleteUI(self.WIN)

        w = cmds.window(self.WIN, title="⬡  Quad Fill Pro",
                        widthHeight=(430, 280), sizeable=True)
        cmds.columnLayout(adj=True, rowSpacing=8, columnOffset=['both', 10])

        cmds.text(
            label=(
                "  ① Select the border edges of your hole\n"
                "  ② Click  [ Preview Grid ]\n"
                "  ③ Tweak Offset & Loop Cuts to align topology\n"
                "  ④ Click  [ Finalize & Merge ]"
            ),
            align='left', height=70, font='smallBoldLabelFont'
        )
        cmds.separator(height=6, style='in')

        # Sliders
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[110, 290])
        cmds.text(label="  Rotation Offset:", align='right')
        self.offset_slider = cmds.intSliderGrp(
            field=True, minValue=0, maxValue=16, value=0,
            changeCommand=self._update, dragCommand=self._update,
            columnWidth=[(1,40),(2,210)])
        cmds.setParent('..')

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[110, 290])
        cmds.text(label="  Loop Cuts:", align='right')
        self.span_slider = cmds.intSliderGrp(
            field=True, minValue=1, maxValue=8, value=4,
            changeCommand=self._update, dragCommand=self._update,
            columnWidth=[(1,40),(2,210)])
        cmds.setParent('..')

        cmds.separator(height=10, style='none')

        # Buttons row
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[130, 170, 100],
                       columnAlign3=['center','center','center'])
        cmds.button(label="① Preview Grid",    height=38, backgroundColor=C["btn_primary"],
                    command=self._start_preview)
        cmds.button(label="② Finalize & Merge", height=38, backgroundColor=C["btn_ok"],
                    command=self._finalize)
        cmds.button(label="✕ Close",            height=38, backgroundColor=C["btn_neutral"],
                    command=self._close)
        cmds.setParent('..')

        cmds.showWindow(w)

    # ── Close ────────────────────────────────────────────────────────────────
    def _close(self, *_):
        if self.preview_plane and cmds.objExists(self.preview_plane):
            cmds.delete(self.preview_plane)
        if cmds.window(self.WIN, exists=True):
            cmds.deleteUI(self.WIN)

    # ── Ordered border verts ─────────────────────────────────────────────────
    def _get_ordered_verts(self, edges):
        adj = {}
        for e in edges:
            evs = cmds.ls(cmds.polyListComponentConversion(e, toVertex=True), flatten=True)
            if len(evs) == 2:
                v1, v2 = evs[0], evs[1]
                adj.setdefault(v1, []).append(v2)
                adj.setdefault(v2, []).append(v1)
        if not adj:
            return [], []
        start = list(adj.keys())[0]
        ordered = [start]
        curr, prev = start, None
        while len(ordered) < len(adj):
            nxt = next((n for n in adj.get(curr, []) if n != prev), None)
            if nxt is None:
                break
            ordered.append(nxt)
            prev, curr = curr, nxt
        positions = [cmds.xform(v, q=True, ws=True, t=True) for v in ordered]
        return positions, ordered

    # ── Preview ──────────────────────────────────────────────────────────────
    def _start_preview(self, *_):
        edges = cmds.ls(selection=True, flatten=True)
        if not edges:
            cmds.warning("⚠ Select border edges first.")
            return
        self.target_mesh = edges[0].split('.')[0]
        vpos, vnames = self._get_ordered_verts(edges)
        if len(vnames) % 2 != 0:
            cmds.warning(f"Edge count ({len(vnames)}) must be even.")
            return
        self.hole_pos   = vpos
        self.hole_verts = vnames
        cmds.intSliderGrp(self.offset_slider, e=True, maxValue=max(1, len(vpos)-1), value=0)
        max_span  = max(1, (len(vpos) // 2) - 1)
        start_span = max(1, max_span // 2)
        cmds.intSliderGrp(self.span_slider, e=True, maxValue=max_span, value=start_span)
        self._update()

    def _update(self, *_):
        if not self.hole_pos:
            return
        offset = cmds.intSliderGrp(self.offset_slider, q=True, v=True)
        Sx     = cmds.intSliderGrp(self.span_slider,   q=True, v=True)
        num_v  = len(self.hole_pos)
        Sy     = int((num_v - 2 * Sx) / 2)
        if Sy < 1:
            cmds.warning("⚠ Invalid span – adjust Loop Cuts.")
            return

        vpos = self.hole_pos[offset:] + self.hole_pos[:offset]

        if self.preview_plane and cmds.objExists(self.preview_plane):
            cmds.delete(self.preview_plane)
        self.preview_plane = cmds.polyPlane(w=1, h=1, sx=Sx, sy=Sy, ch=False,
                                            name="QuadFillPreview")[0]

        # Build boundary index list on the plane
        plane_bnd = []
        for x in range(0, Sx+1):          plane_bnd.append(x)
        for y in range(1, Sy):             plane_bnd.append(y*(Sx+1) + Sx)
        for x in range(Sx, -1, -1):       plane_bnd.append(Sy*(Sx+1) + x)
        for y in range(Sy-1, 0, -1):      plane_bnd.append(y*(Sx+1))

        for k in range(num_v):
            cmds.xform(f"{self.preview_plane}.vtx[{plane_bnd[k]}]",
                       ws=True, t=vpos[k])

        # Coons-patch interior
        c00 = vpos[0]
        c10 = vpos[Sx]
        c11 = vpos[Sx + Sy]
        c01 = vpos[2*Sx + Sy]

        bottom_curve   = vpos[0        : Sx+1]
        right_curve    = vpos[Sx       : Sx+Sy+1]
        top_curve_rev  = list(reversed(vpos[Sx+Sy : 2*Sx+Sy+1]))
        left_curve_rev = list(reversed(vpos[2*Sx+Sy:] + vpos[:1]))

        total = (Sx+1) * (Sy+1)
        bnd_set = set(plane_bnd)
        for idx in range(total):
            if idx in bnd_set:
                continue
            col = idx % (Sx+1)
            row = idx // (Sx+1)
            u = col / float(Sx)
            v = row / float(Sy)
            B = bottom_curve[col]   if col < len(bottom_curve)   else bottom_curve[-1]
            T = top_curve_rev[col]  if col < len(top_curve_rev)  else top_curve_rev[-1]
            L = left_curve_rev[row] if row < len(left_curve_rev) else left_curve_rev[-1]
            R = right_curve[row]    if row < len(right_curve)     else right_curve[-1]
            P = [
                (1-u)*L[i] + u*R[i] + (1-v)*B[i] + v*T[i]
                - ((1-u)*(1-v)*c00[i] + u*(1-v)*c10[i] + (1-u)*v*c01[i] + u*v*c11[i])
                for i in range(3)
            ]
            cmds.xform(f"{self.preview_plane}.vtx[{idx}]", ws=True, t=P)

    # ── Finalize ─────────────────────────────────────────────────────────────
    def _finalize(self, *_):
        if not self.target_mesh or not self.preview_plane \
                or not cmds.objExists(self.preview_plane):
            cmds.warning("⚠ Click 'Preview Grid' first.")
            return
        cmds.select([self.target_mesh, self.preview_plane])
        combined = cmds.polyUnite(ch=False)[0]
        cmds.select(f"{combined}.vtx[*]")
        cmds.polyMergeVertex(d=0.005, ch=False)
        cmds.polyNormal(combined, normalMode=2, ch=False)
        cmds.select(combined)
        self.preview_plane = None
        self.target_mesh   = None
        self.hole_pos      = []
        cmds.inViewMessage(amg="✔  Quad fill merged successfully!", pos="topCenter", fade=True)


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

    w = cmds.window(WIN, title="  Blender Suite Pro  –  Mouad",
                    widthHeight=(440, 760), sizeable=True,
                    backgroundColor=C["window_bg"])

    cmds.scrollLayout(childResizable=True, backgroundColor=C["window_bg"])
    cmds.columnLayout(adj=True, rowSpacing=4, columnOffset=['both', 8])

    # ── MASTER HEADER ───────────────────────────────────────────────────────
    cmds.text(
        label="  ⬡  BLENDER SUITE PRO  –  v2.0",
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

    # ══ QUAD FILL PRO  (TOP PRIORITY) ═══════════════════════════════════════
    _section("⬡", "Quad Fill Pro", C["hdr_quad"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6,
                     borderStyle='etchedIn',
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

    # ══ BEVEL ════════════════════════════════════════════════════════════════
    _section("⬡", "Vertex Bevel", C["hdr_bevel"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(label="  Select corner vertices first.", align='left', height=22)
    _btn("⬡  Vertex Bevel  –  Live Sliders", C["btn_primary"], bevel_live)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ INSET ════════════════════════════════════════════════════════════════
    _section("◈", "Inset Faces", C["hdr_inset"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    cmds.text(label="  Select faces first.", align='left', height=22)
    _btn("◈  Inset Faces  –  Live + Individual Toggle", C["btn_ok"], inset_live)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ EXTRACT ══════════════════════════════════════════════════════════════
    _section("⬡", "Extract", C["hdr_extract"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
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
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    _btn("◎  Shortest Edge Path",  C["btn_neutral"], shortest_path)
    _btn("◎  Select Similar …",    C["btn_neutral"], select_similar_ui)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ SOFT SELECTION ═══════════════════════════════════════════════════════
    _section("⊙", "Proportional / Soft Select", C["hdr_soft"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    _btn("⊙  Soft Selection Controls …", C["btn_neutral"], softselect_tool)
    cmds.setParent('..')
    cmds.setParent('..')

    # ══ DISSOLVE ══════════════════════════════════════════════════════════════
    _section("✂", "Dissolve", C["hdr_dissolve"])
    cmds.frameLayout(labelVisible=False, borderVisible=True,
                     marginWidth=6, marginHeight=6, borderStyle='etchedIn',
                     collapsable=False)
    cmds.columnLayout(adj=True, rowSpacing=4)
    _btn("✂  Dissolve Vertices", C["btn_danger"], dissolve_verts)
    _btn("✂  Dissolve Edges",    C["btn_danger"], dissolve_edges)
    _btn("✂  Dissolve Faces",    C["btn_danger"], dissolve_faces)
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
main_ui()
