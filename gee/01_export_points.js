// 01_export_points.js
// Run ONCE. Creates 1,721 fixed cropland points in Kannur and saves them as an Asset.
// Before running: replace YOUR_PROJECT below with your Google Cloud project ID.

var ASSET_ID = "projects/crop-stress-kannur/assets/kannur_points";

var kannur = ee
  .FeatureCollection("FAO/GAUL/2015/level2")
  .filter(ee.Filter.eq("ADM1_NAME", "Kerala"))
  .filter(ee.Filter.eq("ADM2_NAME", "Kannur"));
print("Kannur features found (expect 1):", kannur.size());

var region = kannur.geometry();
Map.centerObject(region, 9);
Map.addLayer(kannur, { color: "red" }, "Kannur boundary");
// ESA WorldCover class 40 = cropland (1 = cropland, 0 = anything else)
var cropland = ee
  .ImageCollection("ESA/WorldCover/v200")
  .first()
  .select("Map")
  .eq(40);

// Sample directly from the cropland class, 1721 points
var sampled = cropland
  .stratifiedSample({
    numPoints: 0,
    classBand: "Map",
    region: region,
    scale: 100,
    seed: 42,
    classValues: [1],
    classPoints: [1721],
    geometries: true,
    tileScale: 4,
  })
  .randomColumn("r", 42)
  .sort("r")
  .limit(1721);

// Give every point a permanent id and lon/lat columns
var list = sampled.toList(1721);
var points = ee.FeatureCollection(
  ee.List.sequence(0, sampled.size().subtract(1)).map(function (i) {
    var f = ee.Feature(list.get(i));
    var c = f.geometry().coordinates();
    return ee.Feature(f.geometry(), {
      point_id: ee.Number(i).int(),
      lon: c.get(0),
      lat: c.get(1),
    });
  }),
);

print("Points (expect 1721):", points.size());
print("First point:", points.first());
Map.addLayer(points, { color: "yellow" }, "Cropland points");

Export.table.toAsset({
  collection: points,
  description: "kannur_points_asset",
  assetId: ASSET_ID,
});

// Also save a CSV copy for reference / QGIS
Export.table.toDrive({
  collection: points,
  description: "kannur_points_csv",
  folder: "crop_stress_gee",
  fileFormat: "CSV",
  selectors: ["point_id", "lon", "lat"],
});
