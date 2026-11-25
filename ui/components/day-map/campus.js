// The offline schematic of the USask campus (R2): a few hand-placed shapes in lat/long, drawn when map tiles
// can't load (and always in tests and screenshots). APPROXIMATE: footprints are simple rectangles placed by
// hand to within about 100–200 m, roads are rough lines. The map labels it "Schematic · approximate"; it is
// never presented as an accurate map. Only the buildings he goes to are drawn, plus the Bowl and two roads
// for orientation.

// [lat, lon] centre, and the half-size in metres along east (dx) and north (dy)
const rect = (lat, lon, dx, dy) => {
  const dLat = dy / 111_320, dLon = dx / (111_320 * Math.cos((lat * Math.PI) / 180));
  return [[lat + dLat, lon - dLon], [lat + dLat, lon + dLon], [lat - dLat, lon + dLon], [lat - dLat, lon - dLon]];
};

export const CAMPUS = {
  buildings: [
    { id: "maple", name: "Maple Hall", ring: rect(52.1281, -106.6405, 34, 12) },
    { id: "arts", name: "Arts Building", ring: rect(52.1292, -106.6334, 55, 30) },
    { id: "engineering", name: "Engineering Building", ring: rect(52.1326, -106.6284, 70, 45) },
    { id: "thorvaldson", name: "Thorvaldson Building", ring: rect(52.1323, -106.6339, 60, 28) },
  ],
  // the Bowl: the open green in the middle of the old campus
  greens: [{ id: "bowl", name: "The Bowl", ring: rect(52.1309, -106.6352, 85, 55) }],
  // rough lines for orientation only
  roads: [
    { id: "campus-dr", name: "Campus Drive", line: [[52.1345, -106.6305], [52.1310, -106.6300], [52.1282, -106.6312]] },
    { id: "college-dr", name: "College Drive", line: [[52.1352, -106.6420], [52.1349, -106.6330], [52.1347, -106.6240]] },
  ],
};
