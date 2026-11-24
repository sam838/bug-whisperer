# 3D models

Every 3D model in Bug Whisperer is our own, made for it in Blockbench style: cubes with
hand-placed pixels, 32 pixels to a metre. No third-party models or textures are used.

| File (`bb/`) | What it is | Where it appears |
| --- | --- | --- |
| `kane.glb` | Detective Kane: a robot with an old CRT monitor for a head (his eyes glow on its screen), a belted trench coat, a red scarf, a felt fedora and a magnifying glass. Nine moves, eased from pose to pose: Idle (he breathes, looks round and lifts his glass), Walking, Sitting, Standing, Yes, No, Punch, ThumbsUp, Wave. A second, surprised face. | The live office, the reconstruction, the Lineup |
| `desk.glb` | A walnut desk with a green leather top and brass-handled drawers | The live office, the reconstruction |
| `desk_set.glb` | A brass desk lamp, three books, Kane's mug, a telephone, a checklist and a pen | The live office, the reconstruction |
| `armchair.glb` | An oxblood leather club chair with brass studs | The live office |
| `cabinet.glb` | A case-file cabinet: labelled file drawers, shelves of books, a safe, a globe, a trophy | The live office |
| `plant.glb`, `hanging_plant.glb` | A potted monstera and a trailing plant | The live office |
| `wanted_poster.glb` | A framed WANTED poster for a bug | The live office |
| `office_room.glb` | The office itself: teal wallpaper over dark panelling, oak floorboards, a Persian rug | The live office |
| `window.glb` | The tall window's frame, sill and half-drawn blinds | The live office |
| `door.glb` | The door to the app, with KANE DETECTIVE on its glass, the lit corridor behind it, a wall lamp and the board for its sign. The door swings on its hinge (`leaf`) | The live office |
| `wall_clock.glb` | The wall clock; its hands (`hour_hand`, `minute_hand`) keep the viewer's time | The live office |
| `corkboard.glb` | The corkboard under its picture light, with a CASE FILE header, a street map and three status lights | The live office |
| `computer.glb` | Kane's computer: a beige monitor to match his head, a keyboard and a mouse | The live office |
| `side_table.glb` | The side table with the EVIDENCE tray | The live office |
| `recon_room.glb` | The reconstruction's office, with the big corkboard the evidence is pinned to | The reconstruction |
| `lineup_wall.glb` | A 3 m stretch of the Lineup's room: the height chart, the floor and the yellow line, laid side by side | The Lineup |
| `suspect_hoodie.glb`, `suspect_suit.glb`, `suspect_beanie.glb` | The Lineup's three suspects, holding up their placards | The Lineup |

The sources are in [`art/`](../../../art/): `art/models.py` describes every model, and
`python art/models.py` writes both the Blockbench project (`art/<name>.bbmodel`) and the file
the site loads (`whisperer/static/models/bb/<name>.glb`). Only what shows the real case is drawn
in code: the computer's screen, the door's sign, the evidence cards and placards, and the city
outside the window (shrunk to the same big pixels).
