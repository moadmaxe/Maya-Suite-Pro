# ⬡ Maya Suite Pro for Maya

> **Blender-style modeling tools inside Autodesk Maya — built with code vibing.**

A fully open-source Maya Python toolkit that brings the speed and feel of Blender's modeling workflow into Maya. Every tool was designed with one goal: reduce the number of clicks between your idea and your mesh.

---

## 🔓 License & Use

This project is **MIT licensed** — which means you can use it, modify it, bundle it into your own plugins, sell it as part of a commercial toolset, ship it inside a studio pipeline, or build something entirely new on top of it. No strings attached.

> *"Open source is for everyone. If pro TDs want to wrap this into their own shelf tools or paid plugins — go for it. That's exactly what open source is for."*
> — Mouad

The only ask: if you build something cool with it, consider sharing it back. A star, a PR, or even a French translation of the UI goes a long way.

---

## 🛠 How to Use

### Requirements
- **Autodesk Maya 2016 or later** (2020+ recommended)
- Python 2 or 3 (Maya's embedded interpreter — no external packages needed)
- The `modelingToolkit` plugin is loaded automatically on startup

### Installation

**Option A — Run once (Script Editor)**
1. Open Maya's Script Editor (`Windows → General Editors → Script Editor`)
2. Set the tab to **Python**
3. Paste the entire contents of `blender_suite_pro.py`
4. Press `Ctrl+Enter` to execute

**Option B — Add to shelf (permanent)**
1. Run the script once as above
2. In the Script Editor, select all the code
3. Hold `Ctrl` and middle-mouse-drag it onto your shelf
4. Rename the shelf button to anything you like

**Option C — Startup (auto-load every session)**
1. Copy `blender_suite_pro.py` into your Maya scripts directory:
   - Windows: `Documents/maya/<version>/scripts/`
   - macOS/Linux: `~/maya/<version>/scripts/`
2. Add this line to your `userSetup.py`:
   ```python
   import blender_suite_pro
   ```

### Basic Workflow
The main window opens automatically when the script runs. Each section is colour-coded:
- **Blue headers** → creation / preview tools
- **Green buttons** → confirm / apply actions
- **Amber buttons** → tools with side effects (extract, separate)
- **Red buttons** → destructive operations (dissolve)

---

## 🔧 Tools — Deep Dive

---

### ⬡ Quad Fill Pro

**What it does:**
Fills an open polygon hole with a clean, all-quad grid that follows the surface curvature of the surrounding mesh. This is the hardest problem in retopology tooling to solve well, and the reason most Maya users end up doing it manually.

**The logic:**

Maya's built-in Fill Hole (`Mesh → Fill Hole`) produces an n-gon — one huge polygon with as many sides as the hole has edges. That's useless for subdivision workflows. Quad Fill Pro solves this with a two-stage approach:

1. **Topological Edge Walker** — Given a selection of border edges, the tool walks the adjacency graph edge-by-edge to reconstruct the *ordered* boundary loop. This is non-trivial because Maya's selection API returns edges in arbitrary order. The walker builds a dictionary of `{vertex: [neighbors]}` from the edge list, then physically walks the chain from a start vertex, always choosing the neighbor that wasn't the previous step. This guarantees a clean, consecutive boundary with no jumps or duplicates.

2. **Coons Patch Interpolation** — Once the boundary loop is ordered, the tool splits it into four curves (bottom, right, top, left) corresponding to the four sides of the grid. Interior vertex positions are then computed using the **bilinear Coons patch formula**:

   ```
   P(u,v) = (1-u)·L(v) + u·R(v) + (1-v)·B(u) + v·T(u)
            − [(1-u)(1-v)·C00 + u(1-v)·C10 + (1-u)v·C01 + u·v·C11]
   ```

   Where `B`, `T`, `L`, `R` are points sampled along the four boundary curves at parametric coordinates `u` and `v`, and `C00/C10/C01/C11` are the four corner points. The subtracted bilinear term removes the double-counting at corners. The result is a surface that interpolates *exactly* through all boundary points while distributing interior vertices smoothly — no pinching, no sudden direction changes.

3. **Rotation Offset slider** — Because the edge walker picks an arbitrary start vertex, the four boundary curves may be misaligned with the mesh topology. The offset slider rotates the boundary list so you can dial in perfect edge flow alignment before finalising.

4. **Finalize & Merge** — Uses `polyUnite` to combine the preview plane with the target mesh, then `polyMergeVertex` with a small distance threshold to weld the shared boundary verts. A `polyNormal` conform pass fixes any flipped normals from the merge.

**Why pros care:** This is the same mathematical foundation used in NURBS surface patches and subdivision cage construction. Getting quad fills that respect surface curvature is something that typically requires dedicated retopology software. The Coons patch approach does it in ~30 lines of Python.

---

### ⬡ Vertex Bevel — Live Sliders

**What it does:**
Bevels selected vertices into clean chamfers, with live-updating width and segment sliders that stay linked to the construction history node.

**The logic:**

Maya's `polyBevel` command has a well-documented quirk: calling it with `offset` and `segments` flags directly often throws `Invalid flag` errors depending on the Maya version, because the underlying node type differs between edge bevel and vertex bevel. The fix is to call `polyBevel` with *no optional flags at all*, then manually set the node attributes afterwards:

```python
nodes = cmds.polyBevel(selected_verts)
node  = nodes[0]

cmds.setAttr(node + ".vertexComponent", 1)   # forces vertex-bevel mode
cmds.setAttr(node + ".offsetAsFraction", 0)  # use world units, not 0-1 fraction
cmds.setAttr(node + ".offset",   0.2)
cmds.setAttr(node + ".segments", 3)
```

Setting `.vertexComponent = 1` tells Maya's polyBevel node to treat the input as vertex components rather than edges, enabling the star-pattern chamfer. Setting `.offsetAsFraction = 0` ensures the Width slider works in actual scene units rather than a 0–1 normalised fraction (which makes the slider feel broken at typical scene scales).

The live sliders use `attrFieldSliderGrp` with the `attribute` flag pointing directly at the node's `.offset` and `.segments` attributes. This creates a *direct live link* — Maya updates the viewport on every drag frame without any Python callbacks. This is the same mechanism Maya's own Channel Box uses internally.

---

### ◈ Inset Faces — Live + Individual Toggle

**What it does:**
Insets selected faces inward (shrinks them toward their center), with a live offset slider and a toggle between grouped inset (all faces move together, sharing new edge loops) and individual inset (each face insets independently).

**The logic:**

Inset in Maya is implemented via `polyExtrudeFacet` with `localTranslateZ = 0` (no Z extrusion) and the `offset` attribute controlling the inward shrink. The tricky part is reliably getting a reference to the created history node.

The original implementation tried to parse the return value of `polyExtrudeFacet`, but this is fragile — the return includes both the mesh shape and the node, and the order isn't guaranteed. The fix is to call `listHistory` on the mesh *after* the operation and walk backwards through the history stack looking for the first `polyExtrudeFace` node:

```python
history = cmds.listHistory(mesh_name) or []
for n in reversed(history):
    if cmds.nodeType(n) == 'polyExtrudeFace':
        extrude_node = n
        break
```

Reversed history gives us the *most recent* node first, which is always the one we just created.

The `keepFacesTogether` attribute on the node is what controls grouped vs individual behaviour:
- `keepFacesTogether = 1` → all faces share new edge loops (Blender's default "Inset Faces")
- `keepFacesTogether = 0` → each face insets independently into its own island (Blender's "Individual Faces" option, `I` key)

The checkbox passes its value through `int()` before `setAttr` — this matters because Maya's checkbox callback delivers a Python float (`1.0` / `0.0`) and `setAttr` on an integer attribute will silently fail or behave unexpectedly with floats depending on the Maya version.

---

### ⬡ Extract Faces — Live Offset

**What it does:**
Detaches selected faces from the mesh as a separate piece, with an optional offset to physically move them away from the surface. Mirrors Blender's `P → Separate` workflow.

**The logic:**

`polyChipOff` is Maya's detach-faces command. The `dup=True` flag creates a copy of the faces rather than deleting them from the source (if you want destructive extraction, set `dup=False`). The `off` parameter moves the extracted faces along their average normal direction.

The node-based approach means the offset is live and non-destructive until you hit Apply. `polySeparate` then splits the combined mesh into individual transform nodes per shell. The cleanup step (`makeIdentity`, `xform centerPivots`) ensures the extracted pieces have clean transforms and centered pivots, exactly like Blender's behaviour after a separation.

---

### ◎ Select Similar

**What it does:**
Selects all components on the mesh that share a geometric property with the currently selected component — normal direction, face area, edge perimeter length, or topology (valence/connectivity).

**The logic:**

Built on top of `polySelectConstraint`, which is Maya's built-in component filtering system. The tool reads a reference value from the selected component (e.g. the face normal via `polyInfo`), applies it as a constraint, runs the selection in mode 3 (select matching), then *immediately disables the constraint*. That last step is critical — `polySelectConstraint` is a *sticky* global state. If you forget to call `disable=True` after, every subsequent selection in Maya will be filtered by the last constraint, which is one of the most confusing bugs a Maya user can encounter.

The Normal mode parses the vector from `polyInfo`'s text output using a regex (`re.findall`), extracts the last three floats (the XYZ components), and passes them as a direction target to the constraint.

---

### ⊙ Soft Selection Controls

**What it does:**
A focused control panel for Maya's soft/proportional selection — toggle on/off, adjust falloff radius, switch between Volume and Surface falloff modes, and toggle connected-vertices-only mode.

**The logic:**

All controls wrap Maya's `softSelect` command. The volume/surface toggle changes the falloff distance metric: Volume measures straight-line 3D distance through space (can reach through the mesh), Surface measures geodesic distance along the mesh surface (stays on the shell). The connected-only flag further restricts influence to vertices reachable by walking edges from the selection, preventing influence from bleeding across separate mesh islands that happen to be close in 3D space.

---

### ✂ Dissolve (Verts / Edges / Faces)

**What it does:**
Removes topology without creating holes — dissolving an edge merges its two adjacent faces into one, dissolving a vertex merges it into the surrounding edge loop, dissolving a face removes it and leaves the boundary edges.

**The logic:**

- **Dissolve Vertices** → `polyMergeVertex` with a near-zero distance threshold. Using distance=0 would miss floating-point imprecision, so 0.0001 is the safe minimum. `alwaysMergeTwoVertices=True` handles the case where only two vertices share a position.
- **Dissolve Edges** → `polyDelEdge` with `cleanVertices=True`, which automatically dissolves any vertices left over from the deleted edge that would otherwise become 2-valent (connected to only two edges — topologically meaningless in a polygon mesh).
- **Dissolve Faces** → `polyDelFacet`, which removes the face polygon while keeping its boundary edges intact. This is different from Delete, which would leave a hole.

---

## 🤝 Contributing

The best contribution right now is a **French translation** of all UI labels and warning messages. If you speak French, you can make a real difference for French-speaking artists who use this daily.

Other ways to help:
- **Bug reports** — open an Issue with your Maya version and what went wrong
- **Bug fixes** — fork, fix, and open a Pull Request
- **New tools** — Bridge, Loop Select, Relax — anything Blender has that Maya makes painful
- **Maya version testing** — especially 2016–2019 compatibility

---

## 👤 Author

**Mouad**
Built with curiosity, Maya's Python API docs, and a lot of code vibing.

---

*"The best tools are the ones that get out of your way."*
