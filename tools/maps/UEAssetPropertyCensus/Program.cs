using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length < 3 || args.Length > 4)
{
    Console.Error.WriteLine(
        "usage: UEAssetPropertyCensus <shard-root> <mappings.usmap> <output-json> [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var outputPath = args[2];
var sourceGameName = args.Length >= 4 ? args[3] : "ue5.1";

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer =
        new FileUsmapTypeMappingsProvider(mappingsPath)
};

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var packages = provider.Files.Values
    .Where(f => f.IsUePackage)
    .Select(f => f.Path)
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
    .ToArray();

var packageFailures = new List<object>();
var exportFailures = new List<object>();
var classCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);
var propertyNames = new SortedSet<string>(StringComparer.Ordinal);

var packagesLoaded = 0;
var exportsAttempted = 0;
var exportsDecoded = 0;
var exportsWithProperties = 0;
var propertyTagCount = 0;
var generatedExports = 0;
var generatedExportsWithProperties = 0;
var transformPropertyHits = 0;

var transformNames = new HashSet<string>(
    new[]
    {
        "RelativeLocation",
        "RelativeRotation",
        "RelativeScale3D",
        "RootComponent",
        "StaticMesh",
        "AttachParent",
        "OverrideMaterials"
    },
    StringComparer.OrdinalIgnoreCase);

foreach (var packagePath in packages)
{
    try
    {
        var package = provider.LoadPackage(packagePath);
        packagesLoaded++;

        for (var i = 0; i < package.ExportMapLength; ++i)
        {
            exportsAttempted++;

            try
            {
                var export = package.GetExport(i);
                if (export is null)
                {
                    exportFailures.Add(new
                    {
                        packagePath,
                        exportIndex = i,
                        error = "null export"
                    });
                    continue;
                }

                exportsDecoded++;
                classCounts[export.ExportType] =
                    classCounts.GetValueOrDefault(export.ExportType) + 1;

                var isGenerated =
                    export.ExportType.EndsWith(
                        "_C",
                        StringComparison.Ordinal) ||
                    export.ExportType.Contains(
                        "BlueprintGeneratedClass",
                        StringComparison.Ordinal);

                if (isGenerated)
                    generatedExports++;

                if (export.Properties.Count == 0)
                    continue;

                exportsWithProperties++;
                propertyTagCount += export.Properties.Count;

                if (isGenerated)
                    generatedExportsWithProperties++;

                foreach (var property in export.Properties)
                {
                    propertyNames.Add(property.Name.Text);
                    if (transformNames.Contains(property.Name.Text))
                        transformPropertyHits++;
                }
            }
            catch (Exception e)
            {
                exportFailures.Add(new
                {
                    packagePath,
                    exportIndex = i,
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        packageFailures.Add(new
        {
            packagePath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var mappingTypes = provider.MappingsForGame?.Types.Count ?? 0;
var mappingEnums = provider.MappingsForGame?.Enums.Count ?? 0;

var ready =
    packages.Length > 0 &&
    packagesLoaded == packages.Length &&
    packageFailures.Count == 0 &&
    exportFailures.Count == 0 &&
    exportsAttempted > 0 &&
    exportsDecoded == exportsAttempted &&
    propertyTagCount > 0;

var report = new
{
    schemaVersion = 1,
    root = Path.GetFullPath(root),
    sourceGameName,
    mappingTypes,
    mappingEnums,
    packageCount = packages.Length,
    packagesLoaded,
    packageFailureCount = packageFailures.Count,
    exportsAttempted,
    exportsDecoded,
    exportFailureCount = exportFailures.Count,
    exportsWithProperties,
    propertyTagCount,
    generatedExports,
    generatedExportsWithProperties,
    transformPropertyHits,
    uniqueDecodedClassCount = classCounts.Count,
    uniquePropertyNameCount = propertyNames.Count,
    classCounts,
    propertyNameSamples = propertyNames.Take(300).ToArray(),
    packageFailures,
    exportFailures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_PROPERTY_CENSUS " +
    JsonSerializer.Serialize(new
    {
        report.packageCount,
        report.packagesLoaded,
        report.packageFailureCount,
        report.exportsAttempted,
        report.exportsDecoded,
        report.exportFailureCount,
        report.exportsWithProperties,
        report.propertyTagCount,
        report.generatedExports,
        report.generatedExportsWithProperties,
        report.transformPropertyHits,
        report.uniqueDecodedClassCount,
        report.uniquePropertyNameCount,
        report.ready
    }));

foreach (var failure in packageFailures.Take(50))
{
    Console.WriteLine(
        "XZIEL_UE_PROPERTY_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in exportFailures.Take(100))
{
    Console.WriteLine(
        "XZIEL_UE_PROPERTY_EXPORT_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine("XZIEL_UE_PROPERTY_CENSUS_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_PROPERTY_CENSUS_GREEN");
return 0;
