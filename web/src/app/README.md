App shell. Owner: Camilo (PR 1, 10).

- `App.tsx`: full-bleed map with floating panels. Left: top bar and layers. Right: site panel, ending
  above the chat's dock. Bottom centre: the chat's dock, up to 760px wide, whose question box is always
  on screen. The conversation opens above it once something is asked and may lie over the panels beside
  it; maximised, the chat shows its tabs, examples and notes. Bottom left: "What ForeSite doesn't know"
  (its icon alone below 1600px wide, until opened) and the data status line. Above 860px wide the top
  is the search bar's alone and the bottom row is the dock's: `shell.css` places the map's camera
  controls at the left edge in the lower part of the screen, clear of the dock (beside the layers panel
  when it is open), and puts two thin lines under the dock: the note under the map's 3D source switch
  (why a 3D model is not shown), when there is one, and the map credit. It finds these by the map's own
  markup, without editing the map's files, so a change in `features/city_map/CityMap.tsx` to the camera
  block's classes, or to the 3D source switch's label, needs the matching selector changed here. The
  dock steps away during the opening and behind the project screen (`ChatSlot`'s `open`).
- `slots.tsx`: the panel frames other PRs fill. `LayerSlot` (Shandon, PR 5), `SiteSlot` (Camilo, PR 10),
  `ChatSlot` (the chat, PR 9). Replace the body, keep the `MapWindow` frame and its props.
- `MapWindow.tsx`, `map_window.ts`, `map_window.css`: the frame every panel sits in. Its body can be a
  function of the frame's state (minimised, maximised), which is how the chat draws less in a smaller
  frame. It draws the design
  system's `Panel` and adds a title bar to drag, edges and corners to resize, and minimise, maximise and
  put-back buttons (a double-click on the title bar also puts a panel back). The panel last touched is in
  front. A panel that was never moved stays where `shell.css` docks it; a moved one is placed inline.
  Nothing is saved: a reload puts every panel back. Under 860px wide the panels stay docked sheets.
  Moving and resizing need a pointer; there is no keyboard way to do either yet.
- `CommandBar.tsx`: `/` or Cmd/Ctrl-K. Address search through `api.search`, plus app commands.
- `shortcuts.ts`: `/` and Cmd/Ctrl-K search, `L` layers, `C` chat, `T` theme, `?` help, `Esc` closes the
  top panel. Single keys never fire while typing in a field.
- `url_state.ts`: shareable URLs. `?site=<bbl>&layers=1&chat=1`. Picking a site pushes history; panel
  toggles replace it.
- `preferences.ts`: dark or light theme (saved per browser when storage allows) and reduced motion.
