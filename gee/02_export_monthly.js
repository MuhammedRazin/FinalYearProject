// 02_export_monthly.js
// Creates one export task per year. Run each task from the Tasks tab.
// Missing values are written as -9999 (convert to NaN in Python).

var ASSET_ID = 'projects/crop-stress-kannur/assets/kannur_points';
var YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025];
var NODATA = -9999;

var points = ee.FeatureCollection(ASSET_ID);
var region = points.geometry().bounds();
print('Points loaded (expect 1721):', points.size());

var BANDS = ['B3', 'B4', 'B8', 'B11'];
var blank = ee.Image.constant([0, 0, 0, 0]).toFloat().rename(BANDS).selfMask();

function maskS2(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(1).or(scl.eq(3)).or(scl.eq(8))
              .or(scl.eq(9)).or(scl.eq(10)).or(scl.eq(11));
  return img.select(BANDS).divide(10000).toFloat().updateMask(bad.not());
}

function monthImage(year, m) {
  var start = ee.Date.fromYMD(year, m, 1);
  var end = start.advance(1, 'month');

  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region).filterDate(start, end)
    .map(maskS2)
    .merge(ee.ImageCollection([blank]));

  var s2 = col.median();
  var nObs = col.select('B8').count().rename('n_s2');

  var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI');
  var ndmi = s2.normalizedDifference(['B8', 'B11']).rename('NDMI');

  var rain = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
    .filterDate(start, end).select('precipitation').sum().rename('rain_mm');

  var sm = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
    .filterDate(start, end).select('volumetric_soil_water_layer_1')
    .mean().rename('soil_moist');

  var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(region).filterDate(start, end)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
    .select(['VV', 'VH']).mean();

  return s2.select(BANDS)
    .addBands([ndvi, ndwi, ndmi, rain, sm, s1, nObs])
    .unmask(NODATA);
}

var COLUMNS = ['point_id', 'lon', 'lat', 'year', 'month',
               'B3', 'B4', 'B8', 'B11', 'NDVI', 'NDWI', 'NDMI',
               'rain_mm', 'soil_moist', 'VV', 'VH', 'n_s2'];

YEARS.forEach(function (year) {
  var months = ee.List.sequence(1, 12).map(function (m) {
    m = ee.Number(m).int();
    return monthImage(year, m).sampleRegions({
      collection: points,
      properties: ['point_id', 'lon', 'lat'],
      scale: 20,
      tileScale: 4
    }).map(function (f) {
      return f.set({year: year, month: m});
    });
  });

  Export.table.toDrive({
    collection: ee.FeatureCollection(months).flatten(),
    description: 'kannur_monthly_' + year,
    folder: 'crop_stress_gee',
    fileFormat: 'CSV',
    selectors: COLUMNS
  });
});

print('Created tasks for years:', YEARS, '- now open the Tasks tab and click Run on each.');